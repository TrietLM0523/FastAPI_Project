import logging
from dataclasses import dataclass
from typing import Protocol

from fastapi import BackgroundTasks

logger = logging.getLogger("app")


@dataclass(frozen=True)
class AssignmentNotification:
    assignee_email: str
    task_title: str
    project_name: str
    assigned_by: str
    task_id: int


class NotificationSender(Protocol):
    async def send_assignment(self, notification: AssignmentNotification) -> None: ...


class NotificationScheduler(Protocol):
    def schedule(self, notification: AssignmentNotification) -> None: ...


class LoggingEmailSender:
    async def send_assignment(self, notification: AssignmentNotification) -> None:
        logger.info(
            "Task assignment notification",
            extra={
                "task_id": notification.task_id,
                "assignee_email": notification.assignee_email,
                "project_name": notification.project_name,
                "assigned_by": notification.assigned_by,
            },
        )


async def send_assignment_safely(
    sender: NotificationSender, notification: AssignmentNotification
) -> None:
    try:
        await sender.send_assignment(notification)
    except Exception:
        logger.exception(
            "Task assignment notification failed",
            extra={"task_id": notification.task_id},
        )


class BackgroundNotificationScheduler:
    def __init__(
        self, background_tasks: BackgroundTasks, sender: NotificationSender
    ) -> None:
        self.background_tasks = background_tasks
        self.sender = sender

    def schedule(self, notification: AssignmentNotification) -> None:
        self.background_tasks.add_task(
            send_assignment_safely, self.sender, notification
        )


class NullNotificationScheduler:
    def schedule(self, notification: AssignmentNotification) -> None:
        return None
