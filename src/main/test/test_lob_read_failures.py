import pytest

from backend.app.utils import read_text_value


def test_unreadable_lob_is_not_returned_as_fake_text():
    class UnreadableLob:
        def read(self):
            raise OSError("LOB read failed")

        def __str__(self):
            return "LOB object representation"

    with pytest.raises(OSError, match="LOB read failed"):
        read_text_value(UnreadableLob())
