import math

import click
import numpy as np
from shapely.geometry import Polygon, MultiLineString, Point, LineString
from shapely.ops import split, linemerge
from shapely.affinity import rotate
import vpype as vp

def _generate_fill(poly: Polygon, pen_width: float, gap_width: float, angle: float) -> vp.LineCollection:

    min_x, min_y, max_x, max_y = rotate(poly, -angle, poly.centroid).bounds
    height = max_y - min_y
    line_count = math.ceil(height / (pen_width + gap_width)) + 1
    base_seg = np.array([min_x, max_x])
    y_start = min_y + (height - (line_count - 1) * (pen_width + gap_width)) / 2

    segs = []
    for n in range(line_count):
        seg = base_seg + (y_start + (pen_width + gap_width) * n) * 1j
        segs.append(seg if n % 2 == 0 else np.flip(seg))

    segments = MultiLineString([[(pt.real, pt.imag) for pt in seg] for seg in segs])
    segments = rotate(segments, angle, poly.centroid)
    mls = segments.intersection(poly)

    boundary_segments = split(poly.boundary, segments)
    
    # go through hatch segments and match them to boundary segments, alternating ends, so they form a continuous line
    new_segs = MultiLineString()
    cont = LineString()
    alternate = True
    if isinstance(mls, LineString):
        if mls.is_empty:
            mls = MultiLineString()
        else:
            mls = MultiLineString([mls])
    for seg in mls:
        added = False
        for bou in boundary_segments:
            if Point(bou.coords[-1 if alternate else 0]).intersects(Point(seg.coords[-1])):
                added = True
                if not new_segs.is_empty:
                    m = linemerge(list(new_segs) + [seg, bou])
                    if isinstance(m, LineString):
                        new_segs = MultiLineString([m])
                    else:
                        new_segs = MultiLineString(m)
                else:
                    m = linemerge([seg, bou])
                    if isinstance(m, LineString):
                        new_segs = MultiLineString([m])
                    else:
                        new_segs = MultiLineString(m)
                alternate = not alternate
                break
        if not added:
            if not new_segs.is_empty:
                m = linemerge(list(new_segs) + [seg])
                if isinstance(m, LineString):
                    new_segs = MultiLineString([m])
                else:
                    new_segs = MultiLineString(m)
            else:
                new_segs = MultiLineString([seg])

    mls = new_segs

    # trying a different fill style
    # mls = MultiLineString()
    # i = 1
    # while True:
    #     inline = Polygon(p.exterior).buffer(-pen_width * (1/2 + i))
    #     i+=1
    #     if not inline.is_empty:
    #         mls = mls.union(inline.boundary)
    #     else:
    #         break

    # mls = mls.intersection(p.buffer(-pen_width / 2))
    # mls = mls.union(p.buffer(-pen_width / 2).boundary)

    lc = vp.LineCollection(mls)
    lc.merge(tolerance=pen_width, flip=True)
    # mls = lc.as_mls()
    # lc = vp.LineCollection(mls)

    return lc


@click.command()
@click.option(
    "-pw",
    "--pen-width",
    type=vp.LengthType(),
    default="0.3mm",
    help="Pen width (default: 0.3mm)",
)
@click.option(
    "-gw",
    "--gap-width",
    type=vp.LengthType(),
    default="0mm",
    help="Gap width (default: 0mm)",
)
@click.option(
    "-a",
    "--angle",
    type=float,
    default="0",
    help="Angle of hatch (default: 0 degrees)",
)
@click.option(
    "-t",
    "--tolerance",
    type=vp.LengthType(),
    default="0.01mm",
    help="Max distance between start and end point to consider a path closed "
    "(default: 0.01mm)",
)
@click.option("-k", "--keep-open", is_flag=True, help="Keep open paths")
@click.option("-ch", "--cross-hatch", is_flag=True, help="Cross hatch at a 90 degree angle")
@vp.layer_processor
def fill(
    lines: vp.LineCollection, pen_width: float, gap_width: float, angle: float, tolerance: float, keep_open: bool, cross_hatch: bool
) -> vp.LineCollection:

    new_lines = vp.LineCollection()
    polys = []
    for line in lines:
        if np.abs(line[0] - line[-1]) <= tolerance:
            polys.append(Polygon([(pt.real, pt.imag) for pt in line]))
        elif keep_open:
            new_lines.append(line)

    # use XOR to combine shapes to allow for cut-outs
    mp = Polygon()
    for poly in polys:
        if poly.is_valid:
            mp = mp.symmetric_difference(poly)

    if mp.geom_type == "Polygon":
        mp = [mp]

    for p in mp:
        # make any lines we draw inside the shape, accounting for the pen width
        p = p.buffer(-pen_width / 2)
        if not p.is_empty:
            new_lines.extend(_generate_fill(p, pen_width, gap_width, angle))
            if cross_hatch:
                new_lines.extend(_generate_fill(p, pen_width, gap_width, angle+90))
            boundary = p.boundary
            new_lines.extend(boundary)

    return new_lines


fill.help_group = "Plugins"
