from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.label import Label, TaskLabel


class LabelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, *, project_id: int, name: str, normalized_name: str, color: str
    ) -> Label:
        label = Label(
            project_id=project_id,
            name=name,
            normalized_name=normalized_name,
            color=color,
        )
        self.session.add(label)
        await self.session.flush()
        return label

    async def get_by_id(self, label_id: int) -> Label | None:
        return await self.session.get(Label, label_id)

    async def get_by_project_and_name(
        self, project_id: int, normalized_name: str
    ) -> Label | None:
        return await self.session.scalar(
            select(Label).where(
                Label.project_id == project_id,
                Label.normalized_name == normalized_name,
            )
        )

    async def list_by_project(self, project_id: int) -> list[Label]:
        statement = (
            select(Label)
            .where(Label.project_id == project_id)
            .order_by(Label.name, Label.id)
        )
        return list((await self.session.scalars(statement)).all())

    async def update(self, label: Label, data: dict[str, object]) -> None:
        for field_name, value in data.items():
            setattr(label, field_name, value)
        await self.session.flush()

    async def delete(self, label: Label) -> None:
        await self.session.delete(label)


class TaskLabelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_link(self, task_id: int, label_id: int) -> TaskLabel | None:
        return await self.session.get(TaskLabel, (task_id, label_id))

    async def attach(self, task_id: int, label_id: int) -> TaskLabel:
        link = TaskLabel(task_id=task_id, label_id=label_id)
        self.session.add(link)
        await self.session.flush()
        return link

    async def detach(self, link: TaskLabel) -> None:
        await self.session.delete(link)

    async def list_labels_for_task(self, task_id: int) -> list[Label]:
        statement = (
            select(Label)
            .join(TaskLabel, TaskLabel.label_id == Label.id)
            .where(TaskLabel.task_id == task_id)
            .order_by(Label.name, Label.id)
        )
        return list((await self.session.scalars(statement)).all())
