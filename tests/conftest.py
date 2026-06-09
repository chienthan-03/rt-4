import pytest
import numpy as np
from moviepy.editor import ColorClip, AudioClip

@pytest.fixture(scope="session")
def sample_video_path(tmp_path_factory):
    """3-second test video with a sine wave audio track."""
    tmp = tmp_path_factory.mktemp("video")
    path = str(tmp / "test.mp4")
    # Create video with visible color
    video = ColorClip(size=(640, 480), color=(0, 100, 200), duration=3)
    # Create sine wave audio (440Hz) so WAV extraction produces non-empty audio
    def make_sine(t):
        # returns audio samples. Since t is a numpy array or single float, handle both.
        # AudioClip in moviepy expects return value to be of shape (N, 2) if stereo or (N, 1) or (N,)
        # t is a numpy array when evaluated.
        # we can compute element-wise:
        s = np.sin(2 * np.pi * 440 * t)
        return np.column_stack([s, s]) if isinstance(t, np.ndarray) else [s, s]
        
    audio = AudioClip(make_sine, duration=3, fps=44100)
    video = video.set_audio(audio)
    video.write_videofile(path, fps=24, logger=None, codec="libx264", audio_codec="aac")
    return path
