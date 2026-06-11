#!/bin/bash
echo "Building nova using self-hosted compiler..."
./nova build nova.nv -o nova
if [ $? -eq 0 ]; then
    echo "Build successful!"
else
    echo "Build failed!"
fi
