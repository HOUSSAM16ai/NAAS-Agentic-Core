# 🚀 Deployment Guide - World-Class AI Microservices Platform

This guide provides step-by-step instructions for deploying the complete AI microservices platform.

## 📋 Prerequisites

### Required Tools
- **Kubernetes Cluster**: v1.28+ (EKS, GKE, AKS, or self-hosted)
- **kubectl**: v1.28+
- **Helm**: v3.12+
- **Istioctl**: v1.20+
- **Docker**: v24.0+ (for local development)

### Cluster Requirements
- **Minimum**: 3 nodes, 16 vCPUs, 64GB RAM
- **Recommended**: 5+ nodes, 32+ vCPUs, 128GB+ RAM
- **GPU Nodes**: For model serving (optional but recommended)
- **Storage**: 2TB+ SSD-backed persistent storage

### Access Requirements
- Cluster admin access
- Container registry access (GitHub Container Registry)
- DNS management (for public endpoints)

## 🎯 Deployment Phases

### Phase 1: Cluster Setup (30 minutes)

#### 1.1 Create Namespaces
```bash
kubectl create namespace ai-services
kubectl create namespace infrastructure
kubectl create namespace observability
kubectl create namespace ai-models
kubectl create namespace argocd
kubectl create namespace istio-system
```

#### 1.2 Label Namespaces for Istio
```bash
kubectl label namespace ai-services istio-injection=enabled
kubectl label namespace ai-models istio-injection=enabled
```

### Phase 2: Install Core Infrastructure (60 minutes)

#### 2.1 Install Istio Service Mesh
```bash
# Download Istio
curl -L https://istio.io/downloadIstio | ISTIO_VERSION=1.20.0 sh -
cd istio-1.20.0
export PATH=$PWD/bin:$PATH

# Install Istio with production profile
istioctl install -f ../infra/k8s/mesh/istio-config.yaml --verify

# Verify installation
kubectl get pods -n istio-system
istioctl verify-install
```

#### 2.2 Install Cert-Manager (for TLS)
```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Wait for cert-manager to be ready
kubectl wait --for=condition=Available deployment/cert-manager -n cert-manager --timeout=300s
```

#### 2.3 Install Kong API Gateway
```bash
helm repo add kong https://charts.konghq.com
helm repo update

helm install kong kong/kong \
  --namespace infrastructure \
  --create-namespace \
  --set ingressController.enabled=true \
  --set proxy.type=LoadBalancer \
  --set admin.enabled=true

# Apply Kong configuration
kubectl apply -f infra/k8s/gateway/kong-config.yaml
```

#### 2.4 Install OpenTelemetry Collector
```bash
kubectl apply -f infra/k8s/otel/collector-deployment.yaml

# Verify
kubectl get pods -n observability -l app=opentelemetry-collector
```

### Phase 3: Install Kafka (45 minutes)

#### 3.1 Install Strimzi Operator
```bash
kubectl create namespace infrastructure
kubectl apply -f 'https://strimzi.io/install/latest?namespace=infrastructure'

# Wait for operator
kubectl wait --for=condition=Ready pod -l name=strimzi-cluster-operator -n infrastructure --timeout=300s
```

#### 3.2 Deploy Kafka Cluster
```bash
kubectl apply -f infra/k8s/kafka/kafka-cluster.yaml

# Wait for Kafka to be ready (this may take 10-15 minutes)
kubectl wait kafka/cogniforge-kafka --for=condition=Ready --timeout=1800s -n infrastructure

# Verify Kafka
kubectl get kafka -n infrastructure
kubectl get pods -n infrastructure | grep kafka
```

### Phase 4: Install Observability Stack (45 minutes)

#### 4.1 Install Prometheus + Grafana
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install kube-prometheus-stack
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace observability \
  --create-namespace \
  --set prometheus.prometheusSpec.retention=15d \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=100Gi \
  --set grafana.adminPassword=admin123

# Apply custom Prometheus config
kubectl apply -f infra/k8s/monitoring/prometheus-config.yaml
```

#### 4.2 Install Jaeger
```bash
helm repo add jaegertracing https://jaegertracing.github.io/helm-charts
helm repo update

helm install jaeger jaegertracing/jaeger \
  --namespace observability \
  --set provisionDataStore.cassandra=false \
  --set storage.type=memory \
  --set collector.service.otlp.grpc.enabled=true
```

#### 4.3 Install Loki
```bash
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

helm install loki grafana/loki-stack \
  --namespace observability \
  --set grafana.enabled=false \
  --set loki.persistence.enabled=true \
  --set loki.persistence.size=100Gi
```

### Phase 5: Deploy AI Model Serving (30 minutes)

#### 5.1 Install KServe
```bash
kubectl apply -f https://github.com/kserve/kserve/releases/download/v0.12.0/kserve.yaml
kubectl apply -f https://github.com/kserve/kserve/releases/download/v0.12.0/kserve-runtimes.yaml

# Wait for KServe to be ready
kubectl wait --for=condition=Ready pod -l control-plane=kserve-controller-manager -n kserve --timeout=300s
```

#### 5.2 Create Model Storage
```bash
# Apply PVCs
kubectl apply -f infra/k8s/kserve/model-storage-pvc.yaml

# Verify PVCs
kubectl get pvc -n ai-models
```

#### 5.3 Deploy Model Inference Services
```bash
# Deploy vLLM inference service
kubectl apply -f infra/k8s/kserve/inference-llm.yaml

# Monitor deployment
kubectl get inferenceservices -n ai-models
kubectl describe inferenceservice textgen-vllm -n ai-models
```

### Phase 6: Deploy AI Microservices (20 minutes)

#### 6.1 Build and Push Images (if needed)
```bash
# Router Service
cd apps/router-service
docker build -t ghcr.io/houssam16ai/my_ai_project/router-service:latest .
docker push ghcr.io/houssam16ai/my_ai_project/router-service:latest

# Embeddings Service
cd ../embeddings-svc
docker build -t ghcr.io/houssam16ai/my_ai_project/embeddings-svc:latest .
docker push ghcr.io/houssam16ai/my_ai_project/embeddings-svc:latest

# Guardrails Service
cd ../guardrails-svc
docker build -t ghcr.io/houssam16ai/my_ai_project/guardrails-svc:latest .
docker push ghcr.io/houssam16ai/my_ai_project/guardrails-svc:latest
```

#### 6.2 Deploy Services
```bash
# Deploy AI Router
kubectl apply -f apps/router-service/k8s/deployment.yaml

# Deploy Embeddings Service
kubectl apply -f apps/embeddings-svc/k8s/

# Deploy Guardrails Service
kubectl apply -f apps/guardrails-svc/k8s/

# Verify deployments
kubectl get pods -n ai-services
kubectl get svc -n ai-services
kubectl get hpa -n ai-services
```

### Phase 7: Install Argo CD & GitOps (30 minutes)

#### 7.1 Install Argo CD
```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for Argo CD
kubectl wait --for=condition=Available deployment/argocd-server -n argocd --timeout=300s

# Get initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

#### 7.2 Install Argo Rollouts
```bash
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml

# Wait for Argo Rollouts
kubectl wait --for=condition=Available deployment/argo-rollouts -n argo-rollouts --timeout=300s
```

#### 7.3 Configure GitOps Applications
```bash
# Apply Argo CD applications
kubectl apply -f infra/argocd/applications.yaml

# Apply Argo Rollouts configurations
kubectl apply -f infra/argocd/rollouts.yaml

# Verify
kubectl get applications -n argocd
```

### Phase 8: Configure Networking & Ingress (20 minutes)

#### 8.1 Create TLS Certificates
```bash
# Create certificate issuer
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@cogniforge.ai
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
      - http01:
          ingress:
            class: kong
EOF

# Create certificate
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: cogniforge-tls-cert
  namespace: ai-services
spec:
  secretName: cogniforge-tls-cert
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
    - api.cogniforge.ai
    - "*.api.cogniforge.ai"
EOF
```

#### 8.2 Configure DNS
```bash
# Get LoadBalancer IP
GATEWAY_IP=$(kubectl get svc istio-ingressgateway -n istio-system -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

echo "Configure DNS:"
echo "api.cogniforge.ai -> $GATEWAY_IP"
echo "*.api.cogniforge.ai -> $GATEWAY_IP"
```

## ✅ Verification & Testing

### 1. Health Checks
```bash
# Check all pods
kubectl get pods -A | grep -v Running

# Check services
kubectl get svc -n ai-services
kubectl get inferenceservices -n ai-models

# Check Istio
istioctl analyze -A
```

### 2. Service Testing
```bash
# Test AI Router
curl -X POST https://api.cogniforge.ai/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello"}],
    "routing_strategy": "balanced"
  }'

# Test Embeddings
curl -X POST https://api.cogniforge.ai/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "input": ["Test text"],
    "model": "sentence-transformers/all-MiniLM-L6-v2"
  }'

# Test Guardrails
curl -X POST https://api.cogniforge.ai/v1/guardrails/check \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Test content",
    "checks": ["pii", "toxicity"]
  }'
```

### 3. Observability Dashboards
```bash
# Port forward Grafana
kubectl port-forward -n observability svc/prometheus-grafana 3000:80

# Port forward Jaeger
kubectl port-forward -n observability svc/jaeger-query 16686:16686

# Port forward Argo CD
kubectl port-forward -n argocd svc/argocd-server 8080:443
```

Access dashboards:
- **Grafana**: http://localhost:3000 (admin/admin123)
- **Jaeger**: http://localhost:16686
- **Argo CD**: https://localhost:8080

## 🔧 Troubleshooting

### Pod Not Starting
```bash
kubectl describe pod <pod-name> -n ai-services
kubectl logs <pod-name> -n ai-services
```

### Service Mesh Issues
```bash
istioctl analyze -n ai-services
istioctl proxy-status
kubectl logs -n istio-system <istio-pilot-pod>
```

### Kafka Issues
```bash
kubectl get kafka -n infrastructure
kubectl logs -n infrastructure <kafka-pod> -c kafka
```

## 📊 Monitoring & Alerts

### Key Metrics to Monitor
- Service availability (target: 99.9%+)
- Request latency (P50, P95, P99)
- Error rates
- Resource utilization (CPU, memory, GPU)
- Kafka lag
- Model inference time

### Alert Configuration
Alerts are pre-configured in Prometheus. View them at:
```bash
kubectl port-forward -n observability svc/prometheus-kube-prometheus-prometheus 9090:9090
```

Access: http://localhost:9090/alerts

## 🚀 Next Steps

1. **Scale Testing**: Run load tests with k6
2. **Chaos Engineering**: Execute chaos experiments
3. **Security Hardening**: Enable additional security features
4. **Cost Optimization**: Review and optimize resource requests
5. **Custom Models**: Add your own models to KServe

## 📚 Additional Resources

- [Platform Documentation](../docs/MICROSERVICES_PLATFORM.md)
- [Architecture Decision Records](../docs/adr/)
- [API Documentation](../docs/api/)
- [Runbooks](../docs/runbooks/)

---

**Deployment complete! 🎉**

You now have a world-class AI microservices platform running in production!
