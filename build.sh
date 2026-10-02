#!/bin/bash
# Build to a temp output first so a broken build never overwrites the working compiler.
echo "Building nova using self-hosted compiler..."
if ./nova build nova.nv -o nova.new; then
    mv -f nova.new nova
    echo "Build successful!"
else
    rm -f nova.new
    echo "Build failed! Existing ./nova left untouched."
    exit 1
fi
