/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package org.apache.flink.python.api.io;

import org.apache.flink.core.fs.FileInputSplit;
import org.apache.flink.core.fs.FileStatus;
import org.apache.flink.core.fs.Path;
import org.apache.flink.python.api.PythonPlanBinder;
import org.apache.flink.python.api.streaming.io.PythonSplitGeneratorStreamer;

import java.io.IOException;
import java.io.Serializable;

import static org.apache.flink.python.api.PythonPlanBinder.FLINK_PYTHON_DC_ID;

public class PythonInputSplitGenerator implements Serializable {
	private final int id;
	private final Path path;
	private final String filter;
	private final String planArguments;

	public PythonInputSplitGenerator(int id, Path path, String filter) {
		this.id = id;
		this.path = path;
		this.filter = filter;
		this.planArguments = PythonPlanBinder.arguments.toString();
	}

	public FileInputSplit[] createInputSplits(int minNumSplits) throws IOException {
		String tmpPath = System.getProperty("java.io.tmpdir") + "/" + FLINK_PYTHON_DC_ID;

		PythonSplitGeneratorStreamer streamer = new PythonSplitGeneratorStreamer();
		streamer.open(tmpPath, planArguments, this.id);
		streamer.sendRecord(minNumSplits);
		streamer.sendRecord(this.path.toString());


		int numSplits = (Integer) streamer.getRecord(true);

		FileInputSplit[] splits = new FileInputSplit[numSplits];
		for (int x = 0; x < numSplits; x++) {
			String path = (String) streamer.getRecord();
			int from = (Integer) streamer.getRecord(true);
			int to = (Integer) streamer.getRecord(true);

			int numHosts = (Integer) streamer.getRecord(true);
			String[] hosts = new String[numHosts];
			for (int y = 0; y < numHosts; y++) {
				hosts[y] = (String) streamer.getRecord();
			}

			splits[x] = new FileInputSplit(x, new Path(path), from, to, hosts);
		}
		streamer.close();
		return splits;
	}

	protected boolean acceptFile(FileStatus fileStatus) {
		String name = fileStatus.getPath().getName();
		return name.matches(this.filter);
	}
}
