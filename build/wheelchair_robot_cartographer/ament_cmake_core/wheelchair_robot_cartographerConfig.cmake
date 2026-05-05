# generated from ament/cmake/core/templates/nameConfig.cmake.in

# prevent multiple inclusion
if(_wheelchair_robot_cartographer_CONFIG_INCLUDED)
  # ensure to keep the found flag the same
  if(NOT DEFINED wheelchair_robot_cartographer_FOUND)
    # explicitly set it to FALSE, otherwise CMake will set it to TRUE
    set(wheelchair_robot_cartographer_FOUND FALSE)
  elseif(NOT wheelchair_robot_cartographer_FOUND)
    # use separate condition to avoid uninitialized variable warning
    set(wheelchair_robot_cartographer_FOUND FALSE)
  endif()
  return()
endif()
set(_wheelchair_robot_cartographer_CONFIG_INCLUDED TRUE)

# output package information
if(NOT wheelchair_robot_cartographer_FIND_QUIETLY)
  message(STATUS "Found wheelchair_robot_cartographer: 2.1.2 (${wheelchair_robot_cartographer_DIR})")
endif()

# warn when using a deprecated package
if(NOT "" STREQUAL "")
  set(_msg "Package 'wheelchair_robot_cartographer' is deprecated")
  # append custom deprecation text if available
  if(NOT "" STREQUAL "TRUE")
    set(_msg "${_msg} ()")
  endif()
  # optionally quiet the deprecation message
  if(NOT ${wheelchair_robot_cartographer_DEPRECATED_QUIET})
    message(DEPRECATION "${_msg}")
  endif()
endif()

# flag package as ament-based to distinguish it after being find_package()-ed
set(wheelchair_robot_cartographer_FOUND_AMENT_PACKAGE TRUE)

# include all config extra files
set(_extras "")
foreach(_extra ${_extras})
  include("${wheelchair_robot_cartographer_DIR}/${_extra}")
endforeach()
