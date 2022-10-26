#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import importlib.machinery
modulename = importlib.machinery.SourceFileLoader('getMeas',os.path.abspath("/var/www/html/getMeas.py")).load_module()

modulename.AvgCalc_hour()