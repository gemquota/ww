# Blue/Green Deployment — V6-I3#3

## Strategy
- **Blue**: Current production environment
- **Green**: Staged replacement with new version

## Deployment Steps
1. Deploy new version to Green environment
2. Run smoke tests against Green
3. Switch load balancer from Blue → Green
4. Monitor for 15 minutes
5. If issues: switch back to Blue (immediate rollback)
6. Keep Blue as backup for 24 hours

## Requirements
- Stateless application (all state in DB)
- Two identical infrastructure stacks
- Load balancer with instant switch capability

## Rollback
- Instant: Switch load balancer back
- If DB schema changed: Run migration rollback first
- Verify: Run health checks on Blue
