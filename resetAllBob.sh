#!/bin/bash

cd ~/new_server

# 判断当前路径是否有log文件夹，没有则创建
if [ ! -d "log" ]; then
    mkdir log

python3 resetAllBob.py > log/resetAllBob.log
