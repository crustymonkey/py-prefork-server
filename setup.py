#!/usr/bin/env python

#
#    Author: Jay Deiman
#    Email: admin@splitstreams.com
# 
#    This file is part of py-prefork-server.
#
#    py-prefork-server is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    py-prefork-server is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with py-prefork-server.  If not, see <http://www.gnu.org/licenses/>.
#


from distutils.core import setup

setup(name='py-prefork-server' ,
    version='0.1.1' ,
    author='Jay Deiman' ,
    author_email='admin@splitstreams.com' ,
    url='http://stuffivelearned.org/doku.php?id=programming:python:py-prefork-server' ,
    description='A simple tcp/udp prefork server library loosely modelled '
        'after perl\'s Net::Server::Prefork' ,
    long_description='Full documentatation is available at: '
        'http://stuffivelearned.org/doku.php?id=programming:python:py-prefork-server' ,
    packages=['preforkserver'] ,
    package_dir={'preforkserver': 'preforkserver'} ,
    data_files=[ ('share/preforkserver' , 'examples/*') ] ,
    classifiers=[
        'Development Status :: 4 - Beta' ,
        'Environment :: No Input/Output (Daemon)' ,
        'Intended Audience :: System Administrators' ,
        'Intended Audience :: Information Technology' ,
        'License :: OSI Approved :: GNU General Public License (GPL)' ,
        'Natural Language :: English' ,
        'Operating System :: POSIX' ,
        'Programming Language :: Python' ,
        'Topic :: System :: Systems Administration' ,
        'Topic :: System' ,
    ]
)
