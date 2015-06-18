http://securitee.org/teaching/cse508/projects/project1.html


INSTRUCTIONS
------------

[Language]
 - Python 2.7


[Environment]
 - Ubuntu 14.04


[Dependency]
 - Web: Django 1.7.5, Bootstrap 3.3.4, jQuery 1.11.1, Google Chart (calls Google API online)
 - Database: MySQL 5.6
 - Communication: Protocol Buffer 3.0.0-alpha-1, gRPC
 - Network packet manipulation: Scapy 2.3.1


[Preparation]

Ubuntu:
1. python 2.7
    $ sudo apt-get install python2.7

2. pip
    $ sudo apt-get install python-pip    

3. Django 1.7.5
    $ sudo pip install Django==1.7.5

4. Protocol Buffer 3.0.0-alpha-1 Compiler
    check lib directory and find protobuf-cpp-3.0.0-alpha-1.tar.gz     
    $ tar xvf protobuf-cpp-3.0.0-alpha-1.tar.gz
    $ cd protobuf-3.0.0-alpha-1
    $ ./configure
    $ make
    $ make check
        (should pass all the test cases)
    $ sudo make install
    $ protoc --version
        (it shows libprotoc 3.0.0)
        (if report error: "protoc: error while loading shared libraries: libprotoc.so.9: cannot open shared object file: No such file or directory"
         execute: $ sudo ldconfig)

5. gRPC
    check lib directory and find grpc.tar.gz
    $ tar xvf grpc.tar.gz (or: git clone git@github.com:grpc/grpc.git)
    $ apt-get install build-essential autoconf libtool
    $ apt-get install python-all-dev python-virtualenv
    $ cd grpc
    $ git submodule update --init
    $ make 
    $ sudo make install
    $ tools/run_tests/build_python.sh   
        (Use build_python.sh to build the Python code and install it into a virtual environment)
    $ sudo pip install enum34==1.0.4
    $ sudo pip install futures==2.2.0
    $ sudo pip install protobuf==3.0.0-alpha-1
    $ sudo pip install src/python/src  
    $ sudo gedit ~/.profile   (set environment variable for grpc directory)
        add "export GRPC_ROOT=~/Software/grpc"  ("~/Software/grpc" should be your own grpc directory)

6. Mysql 5.6
    $ sudo apt-get install mysql-server-5.6
    $ sudo apt-get install mysql-client-5.6    
    create a connection localhost:3306
    mysql> CREATE USER 'securityhacker'@'localhost' IDENTIFIED BY '123456';
    mysql> GRANT ALL PRIVILEGES ON * . * TO 'securityhacker'@'localhost';
    mysql> FLUSH PRIVILEGES;
    $ sudo apt-get install libmysqlclient-dev
    $ sudo pip install MySQL-python  (for web server)
    $ sudo $GRPC_ROOT/python2.7_virtual_environment/bin/pip install MySQL-python   (for controller)
    execute config/sqlscript.sql in the database
    
7. Scapy 2.3.1
    $ sudo pip install scapy


[Configuration]
    Configuration file: config/configuration.ini


[Running]
1. Run controller
    $ ./run_controller.sh

2. Run scanner
    $ ./run_scanner.sh <port>
        eg.     ./run_scanner.sh 50001
                ./run_scanner.sh 50002
                        ...

3. Run target server for scanning test
    $ python target_server.py <number of ports> <port1> <port2> <port3> ...
        eg.     python target_server.py 3 20000 20001 20002

4. Run web server
    $ ./run_web.sh
    visit url:  http://127.0.0.1:8000/scanner


