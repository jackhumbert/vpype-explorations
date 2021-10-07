import click
import numpy as np
import vpype as vp

@click.command()
@vp.layer_processor
def opf(
    lines: vp.LineCollection
) -> vp.LineCollection:
    """Insert documentation here.
    """
    new_lines = []
    for line in lines:
        new_lines.append(np.delete(line, len(line)-1))

    return new_lines

opf.help_group = "Plugins"