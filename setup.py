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
from preforkserver import __version__ as version

setup(name='py-prefork-server' ,
    version=version ,
    author='Jay Deiman' ,
    author_email='admin@splitstreams.com' ,
    url='http://stuffivelearned.org' ,
    description='A simple tcp/udp prefork server library loosely modelled '
        'after perl\'s Net::Server::Prefork' ,
    packages=['preforkserver'] ,
    package_dir={'preforkserver': 'preforkserver'} ,
)
