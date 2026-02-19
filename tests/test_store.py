"""Tests for Firestore store operations."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import ProjectSyncState, SyncStatus, TaskSyncState


def _make_doc(data=None, exists=True):
    """Create a mock Firestore document snapshot (sync methods)."""
    doc = MagicMock()
    doc.exists = exists
    doc.to_dict.return_value = data
    return doc


def _make_doc_ref(doc):
    """Create a mock Firestore document reference (async get/set/delete)."""
    doc_ref = MagicMock()
    doc_ref.get = AsyncMock(return_value=doc)
    doc_ref.set = AsyncMock()
    doc_ref.delete = AsyncMock()
    return doc_ref


@pytest.fixture
def mock_firestore_client():
    """Mock Firestore AsyncClient. collection() and document() are sync;
    get/set/delete on doc refs are async."""
    return MagicMock()


@pytest.fixture
def store(mock_firestore_client):
    """Create a FirestoreStore with a mocked Firestore client."""
    with patch("app.store.settings") as mock_settings:
        mock_settings.gcp_project_id = "test-project"
        mock_settings.firestore_namespace = "test-ns"
        from app.store import FirestoreStore

        s = FirestoreStore(project_id="test-project", namespace="test-ns")
        s.client = mock_firestore_client
        return s


def _sample_task_state(**overrides):
    defaults = {
        "todoist_task_id": "task-1",
        "capacities_object_id": "notion-page-1",
        "payload_hash": "abc123",
        "last_synced_at": datetime(2025, 10, 1, tzinfo=timezone.utc),
        "sync_status": SyncStatus.OK,
    }
    defaults.update(overrides)
    return TaskSyncState(**defaults)


def _sample_project_state(**overrides):
    defaults = {
        "todoist_project_id": "proj-1",
        "capacities_object_id": "notion-proj-1",
        "payload_hash": "def456",
        "last_synced_at": datetime(2025, 10, 1, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return ProjectSyncState(**defaults)


# ============================================================================
# Task state CRUD
# ============================================================================


class TestGetTaskState:
    async def test_returns_state_when_found(self, store, mock_firestore_client):
        state_data = _sample_task_state().model_dump()
        doc = _make_doc(data=state_data, exists=True)
        doc_ref = _make_doc_ref(doc)
        mock_firestore_client.collection.return_value.document.return_value = doc_ref

        result = await store.get_task_state("task-1")
        assert result is not None
        assert result.todoist_task_id == "task-1"
        assert result.sync_status == SyncStatus.OK

    async def test_returns_none_when_not_found(self, store, mock_firestore_client):
        doc = _make_doc(exists=False)
        doc_ref = _make_doc_ref(doc)
        mock_firestore_client.collection.return_value.document.return_value = doc_ref

        result = await store.get_task_state("nonexistent")
        assert result is None


class TestSaveTaskState:
    async def test_saves_state(self, store, mock_firestore_client):
        doc_ref = _make_doc_ref(_make_doc())
        mock_firestore_client.collection.return_value.document.return_value = doc_ref

        state = _sample_task_state()
        await store.save_task_state(state)

        doc_ref.set.assert_called_once()
        saved_data = doc_ref.set.call_args[0][0]
        assert saved_data["todoist_task_id"] == "task-1"


class TestDeleteTaskState:
    async def test_deletes_state(self, store, mock_firestore_client):
        doc_ref = _make_doc_ref(_make_doc())
        mock_firestore_client.collection.return_value.document.return_value = doc_ref

        await store.delete_task_state("task-1")
        doc_ref.delete.assert_called_once()


# ============================================================================
# Project state CRUD
# ============================================================================


class TestGetProjectState:
    async def test_returns_state_when_found(self, store, mock_firestore_client):
        state_data = _sample_project_state().model_dump()
        doc = _make_doc(data=state_data, exists=True)
        doc_ref = _make_doc_ref(doc)
        mock_firestore_client.collection.return_value.document.return_value = doc_ref

        result = await store.get_project_state("proj-1")
        assert result is not None
        assert result.todoist_project_id == "proj-1"

    async def test_returns_none_when_not_found(self, store, mock_firestore_client):
        doc = _make_doc(exists=False)
        doc_ref = _make_doc_ref(doc)
        mock_firestore_client.collection.return_value.document.return_value = doc_ref

        result = await store.get_project_state("nonexistent")
        assert result is None


class TestSaveProjectState:
    async def test_saves_project_state(self, store, mock_firestore_client):
        doc_ref = _make_doc_ref(_make_doc())
        mock_firestore_client.collection.return_value.document.return_value = doc_ref

        state = _sample_project_state()
        await store.save_project_state(state)

        doc_ref.set.assert_called_once()
        saved_data = doc_ref.set.call_args[0][0]
        assert saved_data["todoist_project_id"] == "proj-1"


# ============================================================================
# Mark operations
# ============================================================================


class TestMarkTaskArchived:
    async def test_marks_existing_task_as_archived(self, store, mock_firestore_client):
        state_data = _sample_task_state().model_dump()
        doc = _make_doc(data=state_data, exists=True)
        doc_ref = _make_doc_ref(doc)
        mock_firestore_client.collection.return_value.document.return_value = doc_ref

        await store.mark_task_archived("task-1", error_message="completed")

        doc_ref.set.assert_called_once()
        saved_data = doc_ref.set.call_args[0][0]
        assert saved_data["sync_status"] == SyncStatus.ARCHIVED
        assert saved_data["error_message"] == "completed"

    async def test_noop_when_task_not_found(self, store, mock_firestore_client):
        doc = _make_doc(exists=False)
        doc_ref = _make_doc_ref(doc)
        mock_firestore_client.collection.return_value.document.return_value = doc_ref

        await store.mark_task_archived("nonexistent")
        doc_ref.set.assert_not_called()


class TestMarkTaskError:
    async def test_marks_existing_task_as_error(self, store, mock_firestore_client):
        state_data = _sample_task_state().model_dump()
        doc = _make_doc(data=state_data, exists=True)
        doc_ref = _make_doc_ref(doc)
        mock_firestore_client.collection.return_value.document.return_value = doc_ref

        await store.mark_task_error("task-1", "API timeout")

        doc_ref.set.assert_called_once()
        saved_data = doc_ref.set.call_args[0][0]
        assert saved_data["sync_status"] == SyncStatus.ERROR
        assert saved_data["error_message"] == "API timeout"

    async def test_noop_when_task_not_found(self, store, mock_firestore_client):
        doc = _make_doc(exists=False)
        doc_ref = _make_doc_ref(doc)
        mock_firestore_client.collection.return_value.document.return_value = doc_ref

        await store.mark_task_error("nonexistent", "some error")
        doc_ref.set.assert_not_called()


# ============================================================================
# Bulk operations
# ============================================================================


class TestGetAllTaskStates:
    async def test_returns_all_states(self, store, mock_firestore_client):
        state1 = _sample_task_state(todoist_task_id="t1").model_dump()
        state2 = _sample_task_state(todoist_task_id="t2").model_dump()

        doc1 = MagicMock()
        doc1.to_dict.return_value = state1
        doc2 = MagicMock()
        doc2.to_dict.return_value = state2

        async def mock_stream():
            yield doc1
            yield doc2

        collection_ref = MagicMock()
        collection_ref.stream.return_value = mock_stream()
        mock_firestore_client.collection.return_value = collection_ref

        results = await store.get_all_task_states()
        assert len(results) == 2
        assert results[0].todoist_task_id == "t1"
        assert results[1].todoist_task_id == "t2"

    async def test_returns_empty_list_when_no_states(self, store, mock_firestore_client):
        async def mock_stream():
            return
            yield  # make it an async generator

        collection_ref = MagicMock()
        collection_ref.stream.return_value = mock_stream()
        mock_firestore_client.collection.return_value = collection_ref

        results = await store.get_all_task_states()
        assert results == []


class TestGetAllProjectStates:
    async def test_returns_all_project_states(self, store, mock_firestore_client):
        state1 = _sample_project_state(todoist_project_id="p1").model_dump()

        doc1 = MagicMock()
        doc1.to_dict.return_value = state1

        async def mock_stream():
            yield doc1

        collection_ref = MagicMock()
        collection_ref.stream.return_value = mock_stream()
        mock_firestore_client.collection.return_value = collection_ref

        results = await store.get_all_project_states()
        assert len(results) == 1
        assert results[0].todoist_project_id == "p1"


class TestClearAllTaskStates:
    async def test_deletes_all_and_returns_count(self, store, mock_firestore_client):
        doc1 = MagicMock()
        doc1.reference.delete = AsyncMock()
        doc2 = MagicMock()
        doc2.reference.delete = AsyncMock()

        async def mock_stream():
            yield doc1
            yield doc2

        collection_ref = MagicMock()
        collection_ref.stream.return_value = mock_stream()
        mock_firestore_client.collection.return_value = collection_ref

        count = await store.clear_all_task_states()
        assert count == 2
        doc1.reference.delete.assert_called_once()
        doc2.reference.delete.assert_called_once()


# ============================================================================
# Meta / reconcile timestamps
# ============================================================================


class TestReconcileTime:
    async def test_get_returns_timestamp_when_exists(self, store, mock_firestore_client):
        doc = _make_doc(
            data={"last_reconcile_time": "2025-10-01T00:00:00Z"}, exists=True
        )
        doc_ref = _make_doc_ref(doc)
        mock_firestore_client.collection.return_value.document.return_value = doc_ref

        result = await store.get_last_reconcile_time()
        assert result == "2025-10-01T00:00:00Z"

    async def test_get_returns_none_when_not_exists(self, store, mock_firestore_client):
        doc = _make_doc(exists=False)
        doc_ref = _make_doc_ref(doc)
        mock_firestore_client.collection.return_value.document.return_value = doc_ref

        result = await store.get_last_reconcile_time()
        assert result is None

    async def test_set_reconcile_time(self, store, mock_firestore_client):
        doc_ref = _make_doc_ref(_make_doc())
        mock_firestore_client.collection.return_value.document.return_value = doc_ref

        await store.set_last_reconcile_time("2025-10-01T00:00:00Z")
        doc_ref.set.assert_called_once_with(
            {"last_reconcile_time": "2025-10-01T00:00:00Z"}, merge=True
        )


# ============================================================================
# Query by Notion ID
# ============================================================================


class TestGetTaskStateByNotionId:
    async def test_returns_state_when_found(self, store, mock_firestore_client):
        state_data = _sample_task_state().model_dump()
        doc = MagicMock()
        doc.to_dict.return_value = state_data

        async def mock_stream():
            yield doc

        query = MagicMock()
        query.stream.return_value = mock_stream()

        collection_ref = MagicMock()
        collection_ref.where.return_value.limit.return_value = query
        mock_firestore_client.collection.return_value = collection_ref

        result = await store.get_task_state_by_notion_id("notion-page-1")
        assert result is not None
        assert result.todoist_task_id == "task-1"

    async def test_returns_none_when_not_found(self, store, mock_firestore_client):
        async def mock_stream():
            return
            yield

        query = MagicMock()
        query.stream.return_value = mock_stream()

        collection_ref = MagicMock()
        collection_ref.where.return_value.limit.return_value = query
        mock_firestore_client.collection.return_value = collection_ref

        result = await store.get_task_state_by_notion_id("nonexistent")
        assert result is None


# ============================================================================
# Close
# ============================================================================


class TestClose:
    async def test_close_clears_client(self, store):
        assert store.client is not None
        await store.close()
        assert store.client is None

    async def test_close_is_idempotent(self, store):
        await store.close()
        await store.close()  # Should not raise
        assert store.client is None


# ============================================================================
# Collection refs
# ============================================================================


class TestCollectionRefs:
    def test_task_collection_ref(self, store):
        assert store._task_collection_ref() == "test-ns_tasks"

    def test_project_collection_ref(self, store):
        assert store._project_collection_ref() == "test-ns_projects"
