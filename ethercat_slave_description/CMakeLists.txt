cmake_minimum_required(VERSION 3.8)
project(ethercat_slave_description)
find_package(ament_cmake REQUIRED)

install(
  DIRECTORY config
  DESTINATION share/${PROJECT_NAME}
)

install(
  PROGRAMS
    scripts/generate_el6224_from_iodd.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
