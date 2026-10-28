# Engineering Standard Operating Procedure: Zero-Downtime Production Deployment

**Document ID:** ENG-SOP-2026-04  
**Department:** Engineering, Infrastructure  
**Access Level:** `engineering`, `executive`  
**Effective Date:** January 15, 2026  
**Author:** Platform Infrastructure Team  

---

### 1. Purpose & Scope
This Standard Operating Procedure (SOP) defines the mandatory steps for deploying microservices and AI inference pipelines to the production Kubernetes clusters (`prod-us-east-1` and `prod-eu-west-1`). All engineers with merge permissions must adhere to these policies.

### 2. Pre-Deployment Validation Checklist
Before triggering a production deployment via ArgoCD, the deployer must ensure:
1. **Automated Test Coverage:** Unit test line coverage must be >= 85%, and integration tests must pass with zero warnings.
2. **Database Migration Checks:** 
   - All PostgreSQL DDL migrations must be backward-compatible (Expand/Contract pattern).
   - Column deletions or renames must be executed in two separate release cycles.
   - Long-running migrations (> 30 seconds) must use `CONCURRENTLY` for index creation.
3. **Canary Analysis Gate:** The new service image must pass a 15-minute canary deployment in `staging-preview` receiving 5% of mirrored synthetic traffic.

### 3. Deployment Window & Approvals
- Standard deployments are permitted **Monday through Thursday between 10:00 AM and 3:00 PM UTC**.
- Deployments on Friday, weekends, or public holidays are strictly prohibited unless a P0 Incident is declared with written sign-off from the VP of Engineering.
- At least one Senior Site Reliability Engineer (SRE) must be on active pager duty during the rollout.

### 4. Rollback Criteria & Automation
The automated Prometheus rollback trigger will immediately revert the deployment to the previous stable Helm revision if any of the following service-level indicators (SLIs) breach thresholds during a 10-minute window:
- **HTTP 5xx Error Rate:** Exceeds 0.25% of total ingress requests.
- **p95 Latency:** Degrades by more than 35% compared to the 7-day rolling baseline.
- **LLM Gateway Fallback Rate:** Exceeds 5% of total model completions.

### 5. Post-Deployment Verification
1. Run the smoke test suite: `make test-smoke-prod`.
2. Inspect the Datadog dashboard for anomalous memory leaks or elevated CPU throttling.
3. Post the deployment summary link in the `#eng-releases` Slack channel.
