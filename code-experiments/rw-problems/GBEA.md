# Running experiments on the GBEA suites 

[GBEA](http://www.gm.fh-koeln.de/~naujoks/gbea/gamesbench.html) (Game-Benchmark for Evolutionary 
Algorithms) is a collection of four suites of real-world benchmark problems based on the Top Trumps 
and Mario games:

- `rw-top-trumps` and `rw-mario-gan` are single-objective suites containing 10 and 28 functions, 
respectively, and 
- `rw-top-trumps-biobj` and `rw-mario-gan-biobj` are bi-objective suites containing 3 and 10 functions.

More informations about the suites can be found at the
[GBEA website](http://www.gm.fh-koeln.de/~naujoks/gbea/gamesbench_doc.html#abstract), here we give 
the details on running your algorithms on these suites in one of the four COCO-supported languages 
(Python, C/C++, Java, Matlab/Octave).

## Preparation

First download and install COCO following the instructions given [here](https://github.com/ttusar/coco/tree/gbea)
(note that the GBEA branch needs to be installed, do not change to the master branch).

While the GBEA suites are not included in COCO directly, they are automatically downloaded and 
compiled the first time you want to use them, so you don't need to handle them separately. 

Solution evaluations for these four suites is done through socket communication (see [here](README.md) 
for more information). COCO serves as a client sending solutions to the socket server, which makes 
sure the correct function is used to evaluate them. 

IMPORTANT: **The right socket server needs to run in order for the GBEA evaluations to work!** If 
this is not the case, you will be alerted with the message `"Connection failed (host=..., port=...) 
Is the server running?"`

### Running the GBEA socket servers

To run the socket server (in C) for the `rw-top-trumps(-biobj)` suite, call 
```
python do.py run-rw-top-trumps-server <port=N> <force-rw-download=0/1> <skip-build>
```

from COCO repository's root folder. 

To run the socket server (in Python) for the `rw-mario-gan(-biobj)` suite, call 
```
python do.py run-rw-mario-gan-server <port=N> <force-rw-download=0/1> <skip-build>
```

from COCO repository's root folder. 

The port can be specified with `port=N`, but changing the default ports is generally not required. The 
first time the servers are run, all the pertinent data is downloaded (which can take some time). 
If you ever need to re-download the GBEA server data, set `force-rw-download=1`. The `skip-build` 
argument is relevant when you want to parallelize your experiments (see Parallelization below for 
more information). When running normally (and especially the first time), use the command without `skip-build`.

You can continue working on the same console you used to run the socket server (you just might need
to press `enter` first.)

While working, the socket server might reset (you will see messages like the one below). This is 
expected behavior.
```
Socket server (Python) reset
```

### Stopping the GBEA socket servers

All socket servers on default ports can be stopped at the same time by calling 
```
python do.py stop-socket-servers <port=N> 
```

from COCO repository's root folder. If `port` is specified, only the socket at that port is stopped.
If you have run the socket servers without specifying the port, you can also stop them without 
specifying the port.

### Parallelization

If you want to execute experiments in parallel, you also need to run socket servers in parallel. 
The socket server should only be built once, but can then be ran multiple times. To 
achieve this, first build the socket server with either 
```
python do.py build-rw-top-trumps-server <force-rw-download=0/1>
```
or
```
python do.py build-rw-mario-gan-server <force-rw-download=0/1>
```
And then run the server with either 
```
python do.py run-rw-top-trumps-server port=N skip-build
```
or 
```
python do.py run-rw-mario-gan-server port=N skip-build
```
making sure that the port is different for each parallel run and the `skip-build` argument is 
present. 

### Troubleshooting

#### Reusing sockets

If the server is stopped after being run, everything should be fine and you should be able to reuse
the same port immediately. However, on some computers (notably Linux ones), the socket is still busy 
for a while longer and cannot be immediately reused. If you can afford to wait a minute, do so. 
Otherwise, you can specify a different (still available) port when running the socket server. 

Running a socket server on a port that is already being used by another socket server will fail with 
a `"Bind failed"` error. Stop the socket on that port and try again.

#### Downloading suite data

On first use, the data of GBEA suites needs to be downloaded. This is done using the `urllib` library 
and can cause issues on macOS if the certificates are not installed. The error looks something like 
this:
````
ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1056)
````
One way to solve this issue is to install the certificates, another is remove the comments sign from 
the following two lines in `do.py`:
````
# import ssl
# ssl._create_default_https_context = ssl._create_unverified_context
````

## Running an experiment in Python

The easiest way to run an experiment with the algorithm of your choice in Python is to use the 
`rw-example-experiment.py` script from the `code-experiments/build/python` folder. There, you can
replace the random search solver with a more elaborate algorithm and then run the script as 
indicated in its documentation. 

For example, to run the algorithm on the `rw-top-trumps(-biobj)` suite, you can either call
```
python do.py run-rw-top-trumps-server
python code-experiments/build/python/rw_example_experiment.py suite=rw-top-trumps
python do.py stop-socket-servers
```

or  simply 
```
python do.py run-rw-experiment suite=rw-top-trumps
```

from COCO repository's root folder. The latter replaces the three commands above.

The results will be saved to the `code-experiments/build/python/exdata` folder.

**Experiments in Python can be easily parallelized** by setting the number of total batches and the 
current batch as follows (note that the experiment needs to be built first)
```
python do.py build-rw-experiment suite=rw-top-trumps
python do.py run-rw-experiment suite=rw-top-trumps batches=4 batch=1 
python do.py run-rw-experiment suite=rw-top-trumps batches=4 batch=2
python do.py run-rw-experiment suite=rw-top-trumps batches=4 batch=3
python do.py run-rw-experiment suite=rw-top-trumps batches=4 batch=4
```

See the documentation in the `rw-example-experiment.py` file for 
details.

## Running an experiment in C/C++

See the example experiment located in the `code-experiments/build/c` folder. Change the 
suite name and algorithm to adjust the experiment to your needs. Once the experiment is set, 
you can call 
```
python do.py run-rw-top-trumps-server
python do.py run-c
python do.py stop-socket-servers
```

to run the algorithm on the `rw-top-trumps(-biobj)` suite or 
```
python do.py run-rw-mario-gan-server
python do.py run-c
python do.py stop-socket-servers
```

to run it on the `rw-mario-gan(-biobj)` suite.

The results will be saved to the `code-experiments/build/c/exdata` folder.

## Running an experiment in Java

See the example experiment located in the `code-experiments/build/java` folder. Change the 
suite name and algorithm to adjust the experiment to your needs. Once the experiment is set, 
you can call 
```
python do.py run-rw-top-trumps-server
python do.py run-java
python do.py stop-socket-servers
```

to run the algorithm on the `rw-top-trumps(-biobj)` suite or 
```
python do.py run-rw-mario-gan-server
python do.py run-java
python do.py stop-socket-servers
```

to run it on the `rw-mario-gan(-biobj)` suite.

The results will be saved to the `code-experiments/build/java/exdata` folder.

## Running an experiment in Matlab/Octave

See the example experiment located in the `code-experiments/build/matlab` folder. Change the 
suite name and algorithm to adjust the experiment to your needs. Once the experiment is set, 
you can call 
```
python do.py run-rw-top-trumps-server
python do.py run-matlab
python do.py stop-socket-servers
```

to run the algorithm on the `rw-top-trumps(-biobj)` suite or 
```
python do.py run-rw-mario-gan-server
python do.py run-matlab
python do.py stop-socket-servers
```

to run it on the `rw-mario-gan(-biobj)` suite.

Replace `run-matlab` with `run-octave` to run the experiment with Octave instead of Matlab.

The results will be saved to the `code-experiments/build/matlab/exdata` folder.
