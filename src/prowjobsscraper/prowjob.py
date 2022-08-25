from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Final, Optional

import requests
from pydantic import BaseModel, Field, HttpUrl, validator

logger = logging.getLogger(__name__)

# Map job type with the prefix string in job name
_TYPE_PREFIX: Final[dict[str, str]] = {
    "periodic": "periodic-ci",
    "presubmit": "pull-ci",
    "batch": "pull-ci",
    "postsubmit": "branch-ci",
}

# Base prefix for a job name
# e.g.: {branch-ci}-{openshift}-{assisted-service}-{master}-
_JOB_PREFIX: str = "{type}-{org}-{repo}-{branch}-"


class EquinixMetadataOperationSystem(BaseModel):
    slug: str
    imageTag: str = Field(alias="image_tag")


class EquinixMetadata(BaseModel):
    id: str
    hostname: str
    plan: str
    facility: str
    metro: str
    operatingSystem: EquinixMetadataOperationSystem = Field(alias="operating_system")


class ProwJobMetadataLabels(BaseModel):
    cloud: Optional[str] = Field(None, alias="ci-operator.openshift.io/cloud")
    cloudClusterProfile: Optional[str] = Field(
        None, alias="ci-operator.openshift.io/cloud-cluster-profile"
    )
    refsBaseRef: Optional[str] = Field(None, alias="prow.k8s.io/refs.base_ref")
    refsOrg: Optional[str] = Field(None, alias="prow.k8s.io/refs.org")
    refsPull: Optional[str] = Field(None, alias="prow.k8s.io/refs.pull")
    refsRepo: Optional[str] = Field(None, alias="prow.k8s.io/refs.repo")
    rehearseContext: Optional[str] = Field(None, alias="ci.openshift.io/rehearse.context")
    variant: Optional[str] = Field(None, alias="ci-operator.openshift.io/variant")


class ProwJobMetadata(BaseModel):
    labels: ProwJobMetadataLabels


class ProwJobSpec(BaseModel):
    job: str
    type: str


class ProwJobStatus(BaseModel):
    state: Optional[str] = None
    url: Optional[HttpUrl] = None
    startTime: Optional[datetime] = None
    pendingTime: Optional[datetime] = None
    completionTime: Optional[datetime] = None
    build_id: Optional[str] = None
    description: Optional[str] = None


class ProwJob(BaseModel):
    equinixMetadata: Optional[EquinixMetadata] = None
    metadata: ProwJobMetadata
    spec: ProwJobSpec
    status: ProwJobStatus

    @property
    def context(self) -> str:
        # If it is a rehearse job, the context is the job being rehearsed
        if self.metadata.labels.rehearseContext:
            job_name = self.metadata.labels.rehearseContext
            if self.metadata.labels.variant:
                job_name = job_name.removeprefix(f"{self.metadata.labels.variant}-")
            logger.debug(
                "job=%s rehearseContext=%s job_name=%s : %s",
                self.spec.job,
                self.metadata.labels.rehearseContext,
                job_name,
                self,
            )
            return job_name

        if not (
            self.metadata.labels.refsOrg
            and self.metadata.labels.refsRepo
            and self.metadata.labels.refsBaseRef
        ):
            logger.warn("Job name cannot be sanitized %s", self)
            return self.spec.job

        job_prefix = _JOB_PREFIX.format(
            type=_TYPE_PREFIX[self.spec.type],
            org=self.metadata.labels.refsOrg,
            repo=self.metadata.labels.refsRepo,
            branch=self.metadata.labels.refsBaseRef,
        )
        if self.metadata.labels.variant:
            job_prefix = f"{job_prefix}{self.metadata.labels.variant}-"

        job_name = self.spec.job.removeprefix(job_prefix)
        logger.debug(
            "job=%s job_prefix=%s job_name=%s : %s",
            self.spec.job,
            job_prefix,
            job_name,
            self,
        )
        return job_name


class ProwJobs(BaseModel):
    """
    ProwJobs represents the data structure returned by Prow's API
    (e.g.: https://prow.ci.openshift.org/prowjobs.js?omit=annotations,decoration_config,pod_spec)
    """

    items: list[ProwJob]

    @classmethod
    def create_from_url(cls, url: str) -> "ProwJobs":
        r = requests.get(url)
        return cls.create_from_string(r.text)

    @classmethod
    def create_from_string(cls, data: str) -> "ProwJobs":
        jobs = cls.parse_raw(data)
        return jobs
