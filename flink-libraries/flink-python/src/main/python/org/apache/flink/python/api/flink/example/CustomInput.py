################################################################################
#  Licensed to the Apache Software Foundation (ASF) under one
#  or more contributor license agreements.  See the NOTICE file
#  distributed with this work for additional information
#  regarding copyright ownership.  The ASF licenses this file
#  to you under the Apache License, Version 2.0 (the
#  "License"); you may not use this file except in compliance
#  with the License.  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
# limitations under the License.
################################################################################
from __future__ import print_function
import os.path
import sys
import numpy as np
import gdal
from gdalconst import GA_ReadOnly

from flink.connection import Collector
#from flink.example.ImageWrapper import ImageWrapper, IMAGE_TUPLE
from flink.functions.FilterFunction import FilterFunction
from flink.functions.FlatMapFunction import FlatMapFunction
from flink.functions.GroupReduceFunction import GroupReduceFunction
from flink.io.PythonInputFormat import PythonInputFormat
from flink.plan.Constants import INT, STRING, BYTES
from flink.plan.Environment import get_environment


class Tokenizer(FlatMapFunction):
    def flat_map(self, value, collector):
        print("Just a dumb map function")
        collector.collect(value)


class GDALInputFormat(PythonInputFormat):
    def __init__(self, jobID):
        super(GDALInputFormat, self).__init__()
        self.jobID = jobID

    def getFiles(self):
        # get sceneids for jobid:
        # SELECT sceneids FROM scenejobs WHERE id = ?
        # get filenames for sceneids:
        # SELECT filename FROM scenes WHERE id = ?
        # filter bsq?
        files = [
                "file:/opt/gms_sample/227064_000202_BLA_SR.bsq",
                "file:/opt/gms_sample/227064_000321_BLA_SR.bsq"
            ]
        return files

    def computeSplits(self):
        path = self._iterator.next()
        for f in self.getFiles():
            self._collector.collect((f,f))

        self._collector._close()


    def _userInit(self):
        gdal.AllRegister()  # TODO: register the ENVI driver only

    def deliver(self, path, collector):
        print(path)
        ds = gdal.Open(path[5:], GA_ReadOnly)
        if ds is None:
            print('Could not open image', path[5:])
            return
        rows = ds.RasterYSize
        cols = ds.RasterXSize
        bandsize = rows * cols
        bands = ds.RasterCount

        imageData = np.empty(bands * bandsize, dtype=np.int16)
        for j in range(bands):
            band = ds.GetRasterBand(j+1)
            data = np.array(band.ReadAsArray())
            lower = j*bandsize
            upper = (j+1)*bandsize
            imageData[lower:upper] = data.ravel()

        metaData = self.readMetaData(path[5:-4])
        metaBytes = ImageWrapper._meta_to_bytes(metaData)
        bArr = bytearray(imageData)
        retVal = (metaData['scene id'], metaBytes, bArr)
        collector.collect(retVal)

    def readMetaData(self, path):
        headerPath = path+'.hdr'
        f = open(headerPath, 'r')

        if f.readline().find("ENVI") == -1:
            f.close()
            raise IOError("Not an ENVI header.")

        lines = f.readlines()
        f.close()

        dict = {}
        try:
            while lines:
                line = lines.pop(0)
                if '=' not in line or line[0] == ';':
                    continue

                (key, sep, val) = line.partition('=')
                key = key.strip().lower()
                val = val.strip()
                if val and val[0] == '{':
                    txt = val.strip()
                    while txt[-1] != '}':
                        line = lines.pop(0)
                        if line[0] == ';':
                            continue

                        txt += '\n' + line.strip()
                    if key == 'description':
                        dict[key] = txt.strip('{}').strip()
                    else:
                        vals = txt[1:-1].split(',')
                        for j in range(len(vals)):
                            vals[j] = vals[j].strip()
                        dict[key] = vals
                else:
                    dict[key] = val
            return dict
        except:
            raise IOError("Error while reading ENVI file header.")


class Adder(GroupReduceFunction):
    def __init__(self):
        super(Adder, self).__init__()
        self.counter = 0

    def reduce(self, iterator, collector):
        for i in iterator:
            self.counter += 1

        collector.collect(self.counter)


class Filter(FilterFunction):
    def __init__(self):
        super(Filter, self).__init__()
        self.count = 0

    def filter(self, value):
        self.count += 1
        print("Image:", value[0], self.count)
        return True


def main():
    env = get_environment()

    inputFormat = GDALInputFormat(26184107)

    data = env.read_custom("/opt/gms_sample/", ".*?\\.bsq", True,
                           inputFormat, [STRING, BYTES, BYTES])
    # data = env.read_custom("/home/dettmerh/gms_sample/", ".*?\\.bsq", True,
    #                        GDALInputFormat(), (STRING, BYTES, BYTES))

    result = data \
        .flat_map(Tokenizer()) \
        .filter(Filter())

    result.output()

    env.set_parallelism(1)

    env.execute(local=True)


if __name__ == "__main__":
    main()
