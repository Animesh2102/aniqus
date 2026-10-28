# Information Security Incident Response & Data Breach Procedure

**Document ID:** SEC-IRP-2026-V3  
**Department:** Information Security, SRE  
**Access Level:** `engineering`, `executive`  
**Effective Date:** March 1, 2026  

---

### 1. Incident Severity Classifications
- **SEV-1 (Critical Breach):** Active exfiltration of customer PII, financial credentials, or compromise of production root keys. Escalation timeline: Immediate notification within 15 minutes to CISO and Legal.
- **SEV-2 (High Impact):** Suspected unauthorized access to non-sensitive staging data or denial of service targeting the external API gateway. Escalation timeline: 1 hour.
- **SEV-3 (Moderate):** Malware detected on isolated corporate laptop or credential stuffing alerts thwarted by Cloudflare WAF.

### 2. Mandatory Containment Steps (SEV-1)
1. **Network Isolation:** Execute AWS Security Group isolation script: `aws ec2 isolate --instance-id <id>`.
2. **Credential Revocation:** Immediately rotate AWS IAM temporary credentials and revoke all OAuth sessions in Clerk / Okta for compromised accounts.
3. **Forensic Preservation:** Take a point-in-time EBS snapshot before terminating any compromised container or node.
4. **Communication Ban:** Under no circumstances should team members discuss potential breaches on public Slack channels. Use the encrypted Signal group `#incident-alpha`.

### 3. Regulatory Notification Timelines
In compliance with GDPR and US state privacy regulations:
- The Data Protection Officer (DPO) must submit formal notification to the relevant supervisory authority within **72 hours** of confirmed unauthorized personal data access.
- Affected customers must be informed without undue delay if the incident is likely to result in a high risk to their rights and freedoms.
