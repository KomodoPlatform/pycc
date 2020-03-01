cmake_minimum_required(VERSION 3.10)

# set the project name
project(CCKit)

find_package(PythonLibs)

include_directories(${PYTHON_INCLUDE_DIRS})

add_library(cckit SHARED
  cckit.cpp
)
