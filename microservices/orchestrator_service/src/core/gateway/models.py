"""
نماذج البيانات الأساسية للبوابة (Gateway Core Data Models).

يحتوي هذا الملف على تعريفات هياكل البيانات والأنواع المستخدمة في نظام البوابة الذكية.
تم تصميم هذه النماذج لتكون غير قابلة للتغيير (Immutable) قدر الإمكان وتتبع مبدأ "البيانات كعقد" (Data as a Contract).

المبادئ (Principles):
- Type Safety: استخدام أنواع Python الحديثة لضمان سلامة البيانات.
- Documentation: توثيق عربي احترافي يشرح الغرض من كل نموذج.
- Abstraction: فصل تعريف البيانات عن المنطق التنفيذي.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TypedDict

from app.core.types import JSONDict, Metadata


class ProtocolType(Enum):
    """
    أنواع البروتوكولات المدعومة في البوابة.

    تحدد هذه القائمة البروتوكولات التي يمكن للبوابة التعامل معها وتحويلها.
    يتم استخدامها لاختيار المحول (Adapter) المناسب للطلب.
    """

    REST = "rest"
    GRAPHQL = "graphql"
    GRPC = "grpc"
    WEBSOCKET = "websocket"


class RoutingStrategy(Enum):
    """
    استراتيجيات توجيه الطلبات بين الخدمات.

    تحدد الخوارزمية المستخدمة لاختيار أفضل خدمة (أو مزود) لمعالجة الطلب.
    تتراوح من الطرق البسيطة (Round Robin) إلى الذكية (Intelligent).
    """

    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED = "weighted"
    LATENCY_BASED = "latency_based"
    COST_OPTIMIZED = "cost_optimized"
    INTELLIGENT = "intelligent"  # توجيه مبني على الذكاء الاصطناعي والتحليل التنبؤي


class ModelProvider(Enum):
    """
    مزوّدو خدمات الذكاء الاصطناعي.

    قائمة بمزودي النماذج الذين يمكن للبوابة توجيه الطلبات إليهم.
    """

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    COHERE = "cohere"
    HUGGINGFACE = "huggingface"
    LOCAL = "local"
    CUSTOM = "custom"


class CacheStrategy(Enum):
    """
    استراتيجيات التخزين المؤقت (Caching).

    تحدد كيفية تخزين واسترجاع البيانات لتقليل زمن الاستجابة وتكاليف الحوسبة.
    """

    NO_CACHE = "no_cache"
    REDIS = "redis"
    MEMORY = "memory"
    DISTRIBUTED = "distributed"
    INTELLIGENT = "intelligent"  # تخزين ذكي يقرر ماذا يخزن بناءً على أنماط الاستخدام


@dataclass
class GatewayRoute:
    """
    تعريف مسار البوابة وخصائصه.

    يمثل هذا النموذج قاعدة توجيه واحدة تربط نمط مسار (Path Pattern) بخدمة خلفية (Upstream Service).
    يحتوي على إعدادات الأمان، وتقييد المعدل، والتخزين المؤقت الخاصة بهذا المسار.
    """

    route_id: str
    path_pattern: str
    methods: list[str]
    upstream_service: str
    protocol: ProtocolType
    auth_required: bool = True
    rate_limit: int | None = None
    cache_ttl: int | None = None
    metadata: Metadata = field(default_factory=dict)


@dataclass
class UpstreamService:
    """
    إعدادات الخدمة الخلفية (Upstream Service).

    يحتوي على المعلومات اللازمة للاتصال بالخدمة التي تقع خلف البوابة،
    بما في ذلك العنوان الأساسي، وإعدادات الصحة، وقواعد قاطع الدائرة.
    """

    service_id: str
    name: str
    base_url: str
    health_check_url: str
    protocol: ProtocolType
    weight: int = 100
    max_connections: int = 1000
    timeout_ms: int = 30000
    circuit_breaker_threshold: int = 5
    metadata: Metadata = field(default_factory=dict)


@dataclass
class RoutingDecision:
    """
    نتيجة قرار التوجيه.

    يمثل هذا الكائن القرار النهائي الذي اتخذه الموجه الذكي،
    متضمناً الخدمة المختارة، والأسباب (Latnecy, Cost, etc.)، والثقة في القرار.
    """

    service_id: str
    base_url: str
    protocol: ProtocolType
    estimated_latency_ms: float
    estimated_cost: float
    confidence_score: float
    reasoning: str
    metadata: JSONDict = field(default_factory=dict)


@dataclass
class LoadBalancerState:
    """
    تتبع حالة موازن الأحمال.

    يخزن الإحصائيات الحية لكل خدمة للمساعدة في اتخاذ قرارات التوجيه وقاطع الدائرة.
    يتم تحديثه في الوقت الفعلي مع كل طلب.
    """

    service_id: str
    active_connections: int = 0
    total_requests: int = 0
    total_errors: int = 0
    avg_latency_ms: float = 0.0
    last_health_check: datetime | None = None
    is_healthy: bool = True


class ProviderCandidate(TypedDict):
    """
    بيانات المرشح لقرار التوجيه.

    تُستخدم هذه البنية لنقل مؤشرات التكلفة والزمن والصحة والدرجة النهائية
    بين مكونات التوجيه والاستراتيجيات، مع الحفاظ على وضوح التعاقد.
    """

    provider: str
    cost: float
    latency: float
    health_score: float
    score: float


@dataclass
class PolicyRule:
    """
    قاعدة تنفيذ السياسة (Policy Enforcement Rule).

    تمثل شرطاً وإجراءً يجب تطبيقه على الطلبات (مثل الحظر، السماح، أو التحويل).
    تستخدم في محرك السياسات لضمان الامتثال والأمان.
    """

    rule_id: str
    name: str
    condition: str  # تعبير منطقي للتقييم
    action: str  # allow, deny, rate_limit, transform
    priority: int = 100
    enabled: bool = True
    metadata: Metadata = field(default_factory=dict)
