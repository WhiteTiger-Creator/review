#!/bin/bash
mkdir -p /app/src
cp /solution/main.cpp /app/src/main.cpp || exit 1
cd /app || exit 1
rm -rf bin
mkdir -p bin
g++ -std=c++17 -O2 -Wall -o bin/cart src/main.cpp || exit 1
test -x /app/bin/cart || exit 1
echo oracle-build-ok
