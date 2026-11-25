from pathlib import Path

from PIL import Image

from sortd.converters import convert_image, sha256_file


def test_webp_conversion_and_hash(tmp_path: Path) -> None:
    source = tmp_path / "sample.webp"
    Image.new("RGB", (4, 4), "red").save(source, "WEBP")
    output = convert_image(source, "png")
    assert output.suffix == ".png"
    assert sha256_file(output) == sha256_file(output)
