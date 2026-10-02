from review_queue import JsonFileQueue


def test_append_writes_the_review_record(tmp_path):
    """An append writes the review record to the queue file."""
    queue = JsonFileQueue(tmp_path / "review_queue.json")
    record = {"employee_id": "E1003", "request": "stolen laptop", "reason": "theft"}
    assert queue.append(record) == record
    assert queue._read() == [record]


def test_second_append_keeps_the_first_record(tmp_path):
    """A second append with the same employee and request keeps the first record."""
    queue = JsonFileQueue(tmp_path / "review_queue.json")
    first = {"employee_id": "E1003", "request": "stolen laptop", "reason": "theft"}
    second = {"employee_id": "E1003", "request": "stolen laptop", "reason": "again"}
    assert queue.append(first) == first
    assert queue.append(second) == first
    assert queue._read() == [first]
