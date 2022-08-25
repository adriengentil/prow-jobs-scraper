import logging
import re

from prowjobsscraper import equinix, event, prowjob, step

logger = logging.getLogger(__name__)


class Scraper:
    def __init__(
        self,
        event_store: event.EventStoreElastic,
        step_extractor: step.StepExtractor,
        equinix_extractor: equinix.EquinixExtractor,
    ):
        self._event_store = event_store
        self._step_extractor = step_extractor
        self._equinix_extractor = equinix_extractor

    def execute(self, jobs: prowjob.ProwJobs):
        logger.info("%s jobs will be processed", len(jobs.items))

        # filter out non-assisted jobs
        jobs.items = [j for j in jobs.items if self._is_assisted_job(j)]

        # filter out jobs already stored
        known_build_ids = self._event_store.scan_build_ids()
        jobs.items = [j for j in jobs.items if j.status.build_id not in known_build_ids]

        # Retrieve equinix metadata for each job
        self._equinix_extractor.hydrate(jobs)

        # Retrieve executed steps for each job
        steps = self._step_extractor.parse_prow_jobs(jobs)

        # Store jobs and steps into their respective indices
        logger.info("%s jobs will be pushed to ES", len(jobs.items))
        self._event_store.index_prow_jobs(jobs.items)

        logger.info("%s steps will be pushed to ES", {len(steps)})
        self._event_store.index_job_steps(steps)

    @staticmethod
    def _is_assisted_job(j: prowjob.ProwJob) -> bool:
        if not j.spec.job.startswith("rehearse"):
            return False

        if j.status.state not in ("success", "failure"):
            return False
        elif not re.search("openshift.*assisted", j.spec.job):
            return False
        elif "openshift-release-fast-forward" in j.spec.job:
            # exclude fast-forward jobs
            return False
        elif j.status.description and "Overridden" in j.status.description:
            # exclude overridden builds
            # the url points to github instead of prow
            return False

        return True
