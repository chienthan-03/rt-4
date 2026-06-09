from unittest.mock import patch, MagicMock
from backend.sound.crawler import parse_sounds_from_html

SAMPLE_HTML = """
<div class="instant">
  <a class="instant-link" href="/instant/vine-boom/">Vine Boom</a>
  <button data-url="/media/sounds/vine-boom.mp3"></button>
</div>
"""

def test_parse_sounds_from_html():
    sounds = parse_sounds_from_html(SAMPLE_HTML, base_url="https://www.myinstants.com")
    assert len(sounds) == 1
    assert sounds[0]["name"] == "Vine Boom"
    assert "vine-boom.mp3" in sounds[0]["mp3_url"]

def test_parse_sounds_from_onclick_html():
    html = """
    <div class="instant">
      <button class="small-button" onclick="play('/media/sounds/vine-boom.mp3', 'loader', 'slug')"></button>
      <a class="instant-link" href="/en/instant/vine-boom-sound/">VINE BOOM SOUND</a>
    </div>
    """
    sounds = parse_sounds_from_html(html, base_url="https://www.myinstants.com")
    assert len(sounds) == 1
    assert sounds[0]["name"] == "VINE BOOM SOUND"
    assert sounds[0]["mp3_url"] == "https://www.myinstants.com/media/sounds/vine-boom.mp3"
