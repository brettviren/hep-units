# hep-units documentation

hep-units provides the CLHEP **HEP system of units**, with a few additions, to
C++, Python, Jsonnet and JavaScript.  All four products are generated from
the same text files and agree bit for bit.  Each has a `parse()` function that
turns text such as `"1.6 mm/us"` into a number.

```python
import hep_units as u
length = 10*u.cm                    # import: multiply by the unit
speed = u.parse("1.6 mm/us")        # import from text
print((length/speed) / u.us, "us")  # export: divide by the unit -> 62.5 us
```

## Contents

1. [Philosophy](philosophy.md): a quantity is a number in a system of units,
   the two rules (multiply to *import*, divide to *export*) and the
   *units firewall*.  Start here.
2. [The `parse()` language](parse.md): what `parse()` accepts, with examples.
3. Language guides, each with import, export and `parse()` examples:
   - [C++](cpp.md): `#include "hep/units.hpp"`
   - [Python](python.md): `import hep_units as u`
   - [Jsonnet](jsonnet.md): `local u = import 'hep/units.libsonnet';`
   - [JavaScript](javascript.md): `hep-units.js`, with a
     [live demo](demo.html) of `parse()` in the browser
4. [System-of-units files](units-files.md): the `.units` text files that define
   the system, how to extend them with your own files, and how to supply a
   whole system.

Building and installing are described in the top-level
[README](../README.md).

## Reading these pages

The pages are plain Markdown and read well as they are, on a code forge or in
an editor.  They can also be turned into a small web site:

```bash
python docs/build.py                 # writes build/docs/index.html etc.
python docs/build.py -o /some/dir    # elsewhere
```

`docs/build.py` uses [pandoc](https://pandoc.org) if it is installed and the
Python [Markdown](https://pypi.org/project/Markdown/) package otherwise (for
example `uv run --with markdown docs/build.py`).  It converts each page, turns
links between pages into links between HTML files, and copies in the
stylesheet, the [demo](demo.html), `hep-units.js` and any source file a page
links to.  The result is a directory of static files: open `index.html`
directly or serve it from any web server.  From a CMake build tree, the
`docs` target does the same into `<build>/docs`.

The demo also works straight from the source tree: open `docs/demo.html` in a
browser and it loads `../js/hep-units.js`.
