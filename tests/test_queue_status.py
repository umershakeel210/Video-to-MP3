from videotomp3.models.queue_item import ItemStatus


def test_no_audio_status_exists():
    assert ItemStatus.NO_AUDIO.value == "No Audio"


def test_invalid_media_status_exists():
    assert ItemStatus.INVALID_MEDIA.value == "Invalid Media"
