# 🚀 Kubernetes Deployment Guide for ProfessorAI

## 📁 Files Overview

| File | Purpose | What It Does |
|------|---------|--------------|
| `1-namespace.yaml` | Namespace | Creates isolated workspace called "profai" |
| `2-configmap.yaml` | Configuration | Non-secret environment variables (ports, models, etc.) |
| `3-secrets.yaml` | Secrets | **API keys** (BASE64 encoded) - **MUST UPDATE!** |
| `4-persistent-volume.yaml` | Storage | 10GB storage for courses/quizzes data |
| `5-deployment.yaml` | Application | How to run your app (3 replicas, health checks) |
| `6-service.yaml` | Networking | LoadBalancer + ClusterIP services |
| `7-ingress.yaml` | HTTP Routing | Routes web traffic to your app |
| `8-hpa.yaml` | Auto-scaling | Scales 2-10 pods based on CPU/memory |

---

## 🔐 STEP 1: Encode Your API Keys

### Option A: Using PowerShell Script (Easiest)

```powershell
cd k8s
.\encode-secrets.ps1
```

### Option B: Manual Encoding

```powershell
# Encode each key:
$key = "sk-proj-your-actual-openai-key-here"
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($key))

# Copy the output and paste into 3-secrets.yaml
```

### Update `3-secrets.yaml`:

Replace the placeholder values with your Base64-encoded keys:

```yaml
data:
  OPENAI_API_KEY: "c2stcHJvai15b3VyLWFjdHVhbC1rZXk="  # Your encoded key here
  SARVAM_API_KEY: "eW91ci1zYXJ2YW0ta2V5LWhlcmU="    # Your encoded key here
  GROQ_API_KEY: "Z3NrX3lvdXItZ3JvcS1rZXktaGVyZQ=="   # Your encoded key here
```

---

## 🖥️ STEP 2: Enable Kubernetes in Docker Desktop

1. Open **Docker Desktop**
2. Go to **Settings** → **Kubernetes**
3. Check **Enable Kubernetes**
4. Click **Apply & Restart**
5. Wait for Kubernetes to start (green icon)

---

## 🚀 STEP 3: Deploy to Local Kubernetes

### Deploy All Resources:

```bash
# Navigate to project root
cd "C:\Users\Lenovo\OneDrive\Documents\profainew\ProfessorAI_0.2_AWS_Ready\Prof_AI"

# Apply all manifests (in order)
kubectl apply -f k8s/1-namespace.yaml
kubectl apply -f k8s/2-configmap.yaml
kubectl apply -f k8s/3-secrets.yaml
kubectl apply -f k8s/4-persistent-volume.yaml
kubectl apply -f k8s/5-deployment.yaml
kubectl apply -f k8s/6-service.yaml
kubectl apply -f k8s/7-ingress.yaml
kubectl apply -f k8s/8-hpa.yaml

# OR apply all at once:
kubectl apply -f k8s/
```

---

## 📊 STEP 4: Check Deployment Status

### View All Resources:

```bash
# Get all resources in profai namespace
kubectl get all -n profai

# Check pods
kubectl get pods -n profai

# Check services
kubectl get svc -n profai

# Check persistent volume
kubectl get pvc -n profai

# Check horizontal pod autoscaler
kubectl get hpa -n profai
```

### Watch Pods Starting:

```bash
# Watch pods in real-time
kubectl get pods -n profai -w

# You should see:
# NAME                                 READY   STATUS    RESTARTS   AGE
# profai-deployment-xxxxx-yyyyy        1/1     Running   0          2m
# profai-deployment-xxxxx-zzzzz        1/1     Running   0          2m
# profai-deployment-xxxxx-aaaaa        1/1     Running   0          2m
```

---

## 🌐 STEP 5: Access Your Application

### Get LoadBalancer IP:

```bash
kubectl get svc profai-loadbalancer -n profai
```

Output:
```
NAME                   TYPE           CLUSTER-IP      EXTERNAL-IP   PORT(S)
profai-loadbalancer    LoadBalancer   10.96.123.45    localhost     80:30123/TCP,8765:30456/TCP
```

### Access via Browser:

- **Main UI**: http://localhost
- **API Docs**: http://localhost/docs
- **Upload Page**: http://localhost/upload.html
- **WebSocket Test**: http://localhost/profai-websocket-test.html

### Test with cURL:

```bash
# Health check
curl http://localhost/

# Get courses
curl http://localhost/api/courses
```

---

## 📝 STEP 6: View Logs

### View Logs from All Pods:

```bash
# All pods
kubectl logs -n profai -l app=profai --tail=100

# Specific pod
kubectl logs -n profai profai-deployment-xxxxx-yyyyy

# Follow logs (live)
kubectl logs -n profai -l app=profai -f
```

---

## 🔧 Common Commands

### Restart Deployment:

```bash
kubectl rollout restart deployment profai-deployment -n profai
```

### Scale Manually:

```bash
# Scale to 5 replicas
kubectl scale deployment profai-deployment --replicas=5 -n profai
```

### Update ConfigMap:

```bash
# Edit config
kubectl edit configmap profai-config -n profai

# Restart to apply changes
kubectl rollout restart deployment profai-deployment -n profai
```

### Update Secrets:

```bash
# Edit secrets
kubectl edit secret profai-secrets -n profai

# Restart to apply
kubectl rollout restart deployment profai-deployment -n profai
```

### Delete Everything:

```bash
# Delete all resources
kubectl delete namespace profai

# This removes everything in the profai namespace
```

---

## 🧪 Testing Auto-Scaling

### Generate Load:

```bash
# Install hey (HTTP load generator)
# Windows: Download from https://github.com/rakyll/hey/releases

# Generate load
hey -z 2m -c 50 http://localhost/

# Watch HPA scale up
kubectl get hpa -n profai -w
```

You should see pods scaling from 2 → 10 as CPU increases.

---

## 🐛 Troubleshooting

### Pods Not Starting:

```bash
# Describe pod to see error
kubectl describe pod profai-deployment-xxxxx-yyyyy -n profai

# Common issues:
# - ImagePullBackOff: Image not found (update image name in 5-deployment.yaml)
# - CrashLoopBackOff: App crashing (check logs)
# - Pending: Not enough resources or PVC issue
```

### Can't Access via Browser:

```bash
# Check service
kubectl get svc profai-loadbalancer -n profai

# Port forward as alternative
kubectl port-forward -n profai svc/profai-service 5001:5001
# Then access: http://localhost:5001
```

### PVC Not Binding:

```bash
# Check PVC status
kubectl get pvc -n profai

# If pending, check storage class
kubectl get storageclass

# For Docker Desktop, use default storage class
# Edit 4-persistent-volume.yaml and uncomment:
# storageClassName: hostpath
```

### HPA Not Working:

```bash
# Install Metrics Server
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Check metrics
kubectl top nodes
kubectl top pods -n profai
```

---

## ✅ Success Checklist

Before moving to AWS deployment:

- [ ] All pods in Running state
- [ ] Can access app via http://localhost
- [ ] API endpoints return data
- [ ] Logs show no errors
- [ ] HPA shows current/target metrics
- [ ] Can upload PDF and generate course
- [ ] WebSocket connections work
- [ ] Data persists after pod restart

---

## 🚀 Next Steps

Once local K8s testing is complete:

1. **Stage 3 Complete** ✅
2. **Stage 4**: Push image to AWS ECR
3. **Stage 5**: Deploy to AWS ECS (optional)
4. **Stage 6**: Deploy to AWS EKS (production K8s)

---

## 📚 Kubernetes Concepts Learned

1. **Namespace**: Isolated environment for resources
2. **ConfigMap**: Non-secret configuration
3. **Secret**: Encrypted sensitive data
4. **PVC**: Persistent storage claim
5. **Deployment**: Application definition with replicas
6. **Service**: Stable network endpoint
7. **Ingress**: HTTP routing rules
8. **HPA**: Auto-scaling based on metrics
9. **Pods**: Running containers
10. **Replicas**: Multiple instances of your app

---

## 🆘 Need Help?

Common kubectl commands:

```bash
# Get help
kubectl --help
kubectl get --help
kubectl describe --help

# View events
kubectl get events -n profai --sort-by='.lastTimestamp'

# Interactive shell in pod
kubectl exec -it profai-deployment-xxxxx-yyyyy -n profai -- bash

# Copy files from pod
kubectl cp profai/profai-deployment-xxxxx-yyyyy:/app/data/courses/course_output.json ./course_output.json
```
