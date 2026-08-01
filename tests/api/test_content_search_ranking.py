"""اختبارات بحث المحتوى المُرتَّب — D-200.

يُثبِت على قاعدة بيانات حقيقية أنّ `/v1/content/search` صار يُرتِّب بالصلة بدل أن يُعيد
بترتيب الإدراج، وأنّ صنف «`LIKE` يطابق داخل الكلمات» لم يعد ممكناً.

كل شيء هنا على **حلقة الاختبار نفسها** (`async_client` لا `TestClient`): عميلٌ متزامن
يُدير حلقةً ثانية، فتُستعمل نفس اتصالات المجمّع من حلقتين وتنفجر أوّليّات asyncio
المربوطة بحلقةٍ واحدة — عطبُ بنيةٍ اختبارية لا عطبُ منتج.
"""

from __future__ import annotations

from sqlalchemy import text

SEARCH = "/v1/content/search"


async def _seed(db_session, rows: list[tuple[str, str, str]]) -> None:
    for content_id, title, body in rows:
        await db_session.execute(
            text(
                "INSERT INTO content_items (id, type, title, level, subject, year, lang,"
                " md_content, source_path, sha256, updated_at)"
                " VALUES (:id, 'exercise', :title, '3AS', 'mathematics', 2024, 'ar',"
                " :body, '/seed', :sha, CURRENT_TIMESTAMP)"
            ),
            {"id": content_id, "title": title, "body": body, "sha": content_id},
        )
    await db_session.commit()


def _run(event_loop, coro):
    return event_loop.run_until_complete(coro)


def _search(event_loop, async_client, **params) -> dict:
    response = _run(event_loop, async_client.get(SEARCH, params=params))
    assert response.status_code == 200, response.text
    return response.json()


CORPUS = [
    ("complex", "تمرين الأعداد المركبة بكالوريا 2024", "حل المعادلة في مجموعة الاعداد المركبه"),
    ("decay", "التناقص الإشعاعي", "نشاط إشعاعي وزمن نصف العمر"),
    ("geometry", "الهندسة في الفضاء", "شعاع الاتجاه والمستوي"),
    ("probability", "الاحتمالات", "كيس فيه كرات ملونة"),
]


def test_a_short_term_no_longer_matches_inside_a_longer_word(
    event_loop, async_client, db_session
) -> None:
    """
    العطب الحيّ: `LIKE '%شعاع%'` كانت تُطابق «الإشعاعي»، فيجد طالبُ الفيزياء درس هندسة.
    """
    _run(event_loop, _seed(db_session, CORPUS))

    body = _search(event_loop, async_client, q="شعاع")
    assert [item["id"] for item in body["items"]] == ["geometry"]


def test_results_are_ranked_by_relevance_not_insertion_order(
    event_loop, async_client, db_session
) -> None:
    _run(
        event_loop,
        _seed(
            db_session,
            [
                ("mention", "درس عامّ", "نتحدّث هنا قليلاً عن التكامل"),
                ("titled", "التكامل بالتجزئة", "شرح كامل"),
            ],
        ),
    )

    body = _search(event_loop, async_client, q="التكامل")
    assert [item["id"] for item in body["items"]] == ["titled", "mention"]
    assert body["ranking"] == "deterministic_lexical"


def test_arabic_spelling_variants_find_the_same_document(
    event_loop, async_client, db_session
) -> None:
    _run(event_loop, _seed(db_session, CORPUS))

    for query in ("الأعداد المركبة", "الاعداد المركبه", "اعداد مركبة"):
        body = _search(event_loop, async_client, q=query)
        assert [item["id"] for item in body["items"]] == ["complex"], query


def test_the_definite_article_does_not_hide_a_document(
    event_loop, async_client, db_session
) -> None:
    _run(event_loop, _seed(db_session, CORPUS))

    for query in ("احتمالات", "الاحتمالات"):
        body = _search(event_loop, async_client, q=query)
        assert [item["id"] for item in body["items"]] == ["probability"], query


def test_every_result_explains_why_it_appeared(event_loop, async_client, db_session) -> None:
    """النتيجة تحمل درجتها ومصطلحاتها — نتيجةٌ سيّئة يجب أن تكون قابلة للتشخيص."""
    _run(event_loop, _seed(db_session, CORPUS))

    item = _search(event_loop, async_client, q="الأعداد المركبة")["items"][0]
    assert 0.0 < item["relevance"] <= 1.0
    assert item["matched_terms"]


def test_no_match_returns_an_empty_list_rather_than_noise(
    event_loop, async_client, db_session
) -> None:
    _run(event_loop, _seed(db_session, CORPUS))

    body = _search(event_loop, async_client, q="طوبولوجيا جبرية")
    assert body["items"] == []
    assert body["ranking"] == "deterministic_lexical"


def test_a_query_of_only_punctuation_returns_nothing(
    event_loop, async_client, db_session
) -> None:
    _run(event_loop, _seed(db_session, CORPUS))

    assert _search(event_loop, async_client, q="؟؟؟")["items"] == []


def test_browsing_without_a_query_is_declared_unranked(
    event_loop, async_client, db_session
) -> None:
    """
    بلا استعلام لا صلة تُحسَب — ولا تُدَّعى. العقد يُصرِّح بذلك فلا يُخمِّن المستهلك.
    """
    _run(event_loop, _seed(db_session, CORPUS))

    body = _search(event_loop, async_client)
    assert body["ranking"] == "unranked"
    assert len(body["items"]) == len(CORPUS)
    assert all(item["relevance"] is None for item in body["items"])


def test_field_filters_still_apply(event_loop, async_client, db_session) -> None:
    _run(event_loop, _seed(db_session, CORPUS))

    assert _search(event_loop, async_client, subject="physics")["items"] == []
    assert len(_search(event_loop, async_client, subject="mathematics")["items"]) == len(CORPUS)


def test_filters_compose_with_the_query(event_loop, async_client, db_session) -> None:
    _run(event_loop, _seed(db_session, CORPUS))

    assert _search(event_loop, async_client, q="شعاع", subject="physics")["items"] == []
