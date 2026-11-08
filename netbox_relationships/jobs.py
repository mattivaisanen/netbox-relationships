"""
Background job: rebuild the edge index once a day, so derived links stay
right even when a change didn't fire a signal (bulk SQL, restores, a prefix
added under existing IP addresses). Needs NetBox's RQ worker running.
"""
from core.choices import JobIntervalChoices
from netbox.jobs import JobRunner, system_job


@system_job(interval=JobIntervalChoices.INTERVAL_DAILY)
class RebuildRelationshipIndexJob(JobRunner):
    class Meta:
        name = 'Rebuild relationship index'

    def run(self, *args, **kwargs):
        from .edges import rebuild
        counts = rebuild()
        self.logger.info('Edges by origin: %s', ', '.join(f'{k}={v}' for k, v in sorted(counts.items())) or 'none')
