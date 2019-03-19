FROM sd2e/reactors:python3-edge

RUN pip uninstall --yes datacatalog
# COPY datacatalog /datacatalog

RUN pip3 install git+https://github.com/SD2E/python-datacatalog.git@12-managers-sampleset-fails-due-to-recursion-depth-limit

COPY s3helpers.py /s3helpers.py
COPY agavehelpers.py /agavehelpers.py
COPY posixhelpers.py /posixhelpers.py
COPY copyfile.py /copyfile.py
COPY routemsg.py /routemsg.py
