import logging
from typing import Any, Callable, Optional

import plotly.graph_objects as graph_objects  # type: ignore
from slack_sdk import WebClient

from jobsautoreport.report import IdentifiedJobMetrics, JobIdentifier, Report

logger = logging.getLogger(__name__)


class SlackReporter:
    def __init__(self, web_client: WebClient, channel_id: str) -> None:
        self._client = web_client
        self._channel_id = channel_id

    def _post_message(
        self,
        report: Report,
        format_function: Callable[[Report], list[dict[str, Any]]],
        thread_time_stamp: Optional[str],
    ) -> str:
        blocks = format_function(report)
        logger.debug("Message formatted successfully")
        response = self._client.chat_postMessage(
            channel=self._channel_id, blocks=blocks, thread_ts=thread_time_stamp
        )
        response.validate()
        logger.info("Message sent successfully")

        return response["ts"]

    def _upload_file(
        self,
        file_title: str,
        file_path: str,
        filename: str,
        thread_time_stamp: Optional[str],
    ) -> None:
        response = self._client.files_upload(
            channels=[self._channel_id],
            file=file_path,
            filename=filename,
            initial_comment=file_title,
            thread_ts=thread_time_stamp,
        )
        response.validate()
        logger.info("%s was uploaded successfully", filename)

    def send_report(self, report: Report) -> None:
        thread_time_stamp = self._post_message(
            report=report,
            format_function=self._format_header_message,
            thread_time_stamp=None,
        )
        self._post_message(
            report=report,
            format_function=self._format_periodic_comment,
            thread_time_stamp=thread_time_stamp,
        )
        self._upload_most_failing_jobs_graph(
            jobs=report.top_10_failing_e2e_or_subsystem_periodic_jobs,
            file_title="Top 10 Failed Periodic Jobs",
            thread_time_stamp=thread_time_stamp,
        )
        self._post_message(
            report=report,
            format_function=self._format_presubmit_comment,
            thread_time_stamp=thread_time_stamp,
        )
        self._upload_most_failing_jobs_graph(
            jobs=report.top_10_failing_e2e_or_subsystem_presubmit_jobs,
            file_title="Top 10 Failed Presubmit Jobs",
            thread_time_stamp=thread_time_stamp,
        )
        self._create_and_upload_most_triggered_jobs_graph(
            jobs=report.top_5_most_triggered_e2e_or_subsystem_jobs,
            file_title="Top 5 Triggered Presubmit Jobs",
            thread_time_stamp=thread_time_stamp,
        )
        self._post_message(
            report=report,
            format_function=self._format_postsubmit_comment,
            thread_time_stamp=thread_time_stamp,
        )
        self._upload_most_failing_jobs_graph(
            jobs=report.top_10_failing_postsubmit_jobs,
            file_title="Top 10 Failed Postsubmit Jobs",
            thread_time_stamp=thread_time_stamp,
        )
        self._post_message(
            report=report,
            format_function=self._format_equinix_message,
            thread_time_stamp=thread_time_stamp,
        )

    @staticmethod
    def _format_header_message(report: Report) -> list[dict[str, Any]]:
        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "CI Report",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{report.from_date.strftime('%Y-%m-%d %H:%M:%S')} UTC\t:arrow_right:\t{report.to_date.strftime('%Y-%m-%d %H:%M:%S')} UTC*\n",
                },
            },
        ]

    @staticmethod
    def _format_periodic_comment(report: Report) -> list[dict[str, Any]]:
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Periodic e2e/subsystem jobs*\n",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"•\t _{report.number_of_e2e_or_subsystem_periodic_jobs}_ in total\n"
                        f" \t\t *-* :done-circle-check: {report.number_of_successful_e2e_or_subsystem_periodic_jobs} succeeded\n"
                        f" \t\t *-* :x: {report.number_of_failing_e2e_or_subsystem_periodic_jobs} failed\n"
                        f" \t  _{report.success_rate_for_e2e_or_subsystem_periodic_jobs:.2f}%_ *success rate*\n"
                    ),
                },
            },
        ]

    @staticmethod
    def _format_postsubmit_comment(report: Report) -> list[dict[str, Any]]:
        return [
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Postsubmit jobs*\n",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"•\t _{report.number_of_postsubmit_jobs}_ in total\n"
                        f" \t\t *-* :done-circle-check: {report.number_of_successful_postsubmit_jobs} succeeded\n"
                        f" \t\t *-* :x: {report.number_of_failing_postsubmit_jobs} failed\n"
                        f" \t  _{report.success_rate_for_postsubmit_jobs:.2f}%_ *success rate*\n"
                    ),
                },
            },
        ]

    @staticmethod
    def _format_presubmit_comment(report: Report) -> list[dict[str, Any]]:
        return [
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Presubmit e2e/subsystem jobs*\n",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"•\t _{report.number_of_e2e_or_subsystem_presubmit_jobs}_ in total\n"
                        f" \t\t *-* :done-circle-check: {report.number_of_successful_e2e_or_subsystem_presubmit_jobs} succeeded\n"
                        f" \t\t *-* :x: {report.number_of_failing_e2e_or_subsystem_presubmit_jobs} failed\n"
                        f" \t  _{report.success_rate_for_e2e_or_subsystem_presubmit_jobs:.2f}%_ *success rate*\n"
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"•\t _{report.number_of_rehearsal_jobs}_ rehearsal jobs triggered",
                },
            },
        ]

    @staticmethod
    def _format_equinix_message(report: Report) -> list[dict[str, Any]]:
        return [
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Equinix*",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"•\t _{report.total_number_of_machine_leased}_ machine lease attempts\n"
                        f" \t\t *-* :done-circle-check: {report.number_of_successful_machine_leases} succeeded\n"
                        f" \t\t *-* :x: {report.number_of_unsuccessful_machine_leases} failed\n"
                    ),
                },
            },
        ]

    def _upload_most_failing_jobs_graph(
        self,
        jobs: list[IdentifiedJobMetrics],
        file_title: str,
        thread_time_stamp: Optional[str],
    ) -> None:
        is_variant_unique = JobIdentifier.is_variant_unique(
            [identified_job_metrics.job_identifier for identified_job_metrics in jobs]
        )
        names = [
            identified_job_metrics.job_identifier.get_slack_name(is_variant_unique)
            for identified_job_metrics in jobs
        ]
        successes = [
            identified_job_metrics.metrics.successes for identified_job_metrics in jobs
        ]
        failures = [
            identified_job_metrics.metrics.failures for identified_job_metrics in jobs
        ]
        filename, file_path = self._file_name_proccesor(file_title=file_title)
        fig = graph_objects.Figure()
        fig.add_trace(
            graph_objects.Bar(
                x=successes,
                y=names,
                name="succeeded",
                orientation="h",
                marker=dict(
                    color="rgba(90, 212, 90, 0.7)",
                    line=dict(color="rgba(90, 212, 90, 1)", width=3),
                ),
            )
        )

        fig.add_trace(
            graph_objects.Bar(
                x=failures,
                y=names,
                name="failed",
                orientation="h",
                marker=dict(
                    color="rgba(230, 0, 73, 0.7)",
                    line=dict(color="rgba(230, 0, 73, 1.0)", width=3),
                ),
            )
        )

        fig.update_layout(
            barmode="stack",
            title_text="Top 10 Failed Jobs",
            font=dict(family="Times New Roman", size=8),
        )
        fig.write_image(file_path, scale=3)
        logger.info("image created at %s successfully", file_path)

        self._upload_file(
            file_title=file_title,
            filename=filename,
            file_path=file_path,
            thread_time_stamp=thread_time_stamp,
        )

    def _create_and_upload_most_triggered_jobs_graph(
        self,
        jobs: list[IdentifiedJobMetrics],
        file_title: str,
        thread_time_stamp: Optional[str],
    ) -> None:
        is_variant_unique = JobIdentifier.is_variant_unique(
            [identified_job_metrics.job_identifier for identified_job_metrics in jobs]
        )
        names = [
            identified_job_metrics.job_identifier.get_slack_name(is_variant_unique)
            for identified_job_metrics in jobs
        ]
        quantities = [
            identified_job_metrics.metrics.total for identified_job_metrics in jobs
        ]
        filename, file_path = self._file_name_proccesor(file_title=file_title)
        fig = graph_objects.Figure()
        fig.add_trace(
            graph_objects.Bar(
                x=quantities,
                y=names,
                name="succeeded",
                orientation="h",
                marker=dict(
                    color="rgba(26, 83, 255, 0.7)",
                    line=dict(color="rgba(26, 83, 255, 1)", width=3),
                ),
            )
        )
        fig.update_layout(
            title_text="Top 5 Triggered Jobs",
            font=dict(family="Times New Roman", size=10),
        )
        fig.write_image(file_path, scale=3)
        logger.info("image created at %s successfully", file_path)

        self._upload_file(
            file_title=file_title,
            filename=filename,
            file_path=file_path,
            thread_time_stamp=thread_time_stamp,
        )

    @staticmethod
    def _file_name_proccesor(file_title: str) -> tuple[str, str]:
        filename = file_title.replace(" ", "_").lower()
        file_path = f"/tmp/{filename}.png"
        return filename, file_path
