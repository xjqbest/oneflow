"""
Copyright 2020 The OneFlow Authors. All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
from __future__ import absolute_import

import oneflow.python.framework.c_api_util as c_api_util


class IdGenerator(object):
    def NewSymbolId(self):
        raise NotImplementedError

    def NewObjectId(self):
        raise NotImplementedError


class PhysicalIdGenerator(IdGenerator):
    def NewSymbolId(self):
        return c_api_util.NewPhysicalSymbolId()

    def NewObjectId(self):
        return c_api_util.NewPhysicalObjectId()


class LogicalIdGenerator(IdGenerator):
    def NewSymbolId(self):
        return c_api_util.NewLogicalSymbolId()

    def NewObjectId(self):
        return c_api_util.NewLogicalObjectId()
