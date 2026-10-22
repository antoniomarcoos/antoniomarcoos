"""Render the public GitHub contribution calendar; standard library only."""
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import re
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)

class Calendar(HTMLParser):
    def __init__(self):
        super().__init__()
        self.days = {}
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "td" and "data-date" in a and "data-level" in a:
            day = date.fromisoformat(a["data-date"])
            level = int(a["data-level"])
            if level not in range(5):
                raise ValueError("Unexpected contribution level")
            self.days[day] = level

def render(html):
    parser = Calendar()
    parser.feed(html)
    days = sorted(parser.days.items())
    if len(days) < 350 or len(days) > 380:
        raise ValueError(f"Incomplete calendar: {len(days)} days; keeping previous image")
    if (date.today() - days[-1][0]).days not in range(0, 4):
        raise ValueError("Stale calendar; keeping previous image")
    root = ET.fromstring((ROOT / "assets/fellowship-walk.svg").read_text())
    # Reject invalid SMIL translation coordinates before publishing an image.
    for animation in root.iter(f"{NS_PREFIX}animateTransform"):
        if animation.get("type") != "translate":
            continue
        samples = []
        for attribute in ("from", "to", "values"):
            samples.extend(animation.get(attribute, "").split(";"))
        for sample in filter(str.strip, samples):
            numbers = sample.replace(",", " ").split()
            if len(numbers) not in (1, 2):
                raise ValueError(f"Invalid animated translation: {sample!r}")
            for number in numbers:
                float(number)
    for item in list(root):
        if item.tag == f"{NS_PREFIX}rect" and item.get("width") == "12":
            root.remove(item)
    grid = root.find(f"{NS_PREFIX}g[@id='contribution-grid']")
    if grid is None:
        grid = ET.Element(f"{NS_PREFIX}g", {"id": "contribution-grid"})
        background = next(item for item in root if item.tag == f"{NS_PREFIX}rect")
        root.insert(list(root).index(background) + 1, grid)
    else:
        grid.clear()
        grid.set("id", "contribution-grid")
    first = days[0][0]
    sunday = first.toordinal() - ((first.weekday() + 1) % 7)
    palette = ["#17261f", "#274934", "#426d49", "#789252", "#d0b56d"]
    for day, level in days:
        offset = day.toordinal() - sunday
        node = ET.Element(f"{NS_PREFIX}rect", {
            "x": str(48 + (offset // 7) * 17),
            "y": str(95 + (offset % 7) * 17),
            "width": "12", "height": "12", "rx": "2",
            "fill": palette[level], "data-date": day.isoformat(),
            "data-level": str(level),
        })
        ET.SubElement(node, f"{NS_PREFIX}title").text = f"{day.isoformat()} · activity level {level}/4"
        grid.append(node)
    for node in root.iter(f"{NS_PREFIX}text"):
        if node.get("y") == "35":
            node.text = "My GitHub journey"
        elif node.get("y") == "59":
            node.text = f"@antoniomarcoos · {first.isoformat()} — {days[-1][0].isoformat()}"
        elif node.get("y") == "282":
            node.text = "PUBLIC GITHUB DATA · UPDATED " + datetime.now(timezone.utc).strftime("%Y-%m-%d")
    root.find(f"{NS_PREFIX}desc").text = "Real public GitHub contribution calendar for antoniomarcoos with animated vector characters. Colors represent GitHub activity levels."
    return ET.tostring(root, encoding="unicode")

NS_PREFIX = "{" + NS + "}"
if __name__ == "__main__":
    request = urllib.request.Request(
        "https://github.com/users/antoniomarcoos/contributions",
        headers={"User-Agent": "antoniomarcoos-profile-calendar", "Accept": "text/html"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        html = response.read().decode("utf-8")
    svg = render(html)
    output = ROOT / "assets/journey-contributions.svg"
    temp = output.with_suffix(".tmp")
    temp.write_text(svg, encoding="utf-8")
    temp.replace(output)
    print(f"Updated {output.name} from the public GitHub calendar")
