import subprocess
import time
import subprocess
import statistics
import random
import json

EXPERIMENT_TIME = 60*60
SAMPLE_TIME = 30
RESTART_RATIO = 0.2


def getIP(podName):
    proc = subprocess.run(['kubectl', 'exec', podName, '--', 'hostname', '-i'], capture_output=True)
    return str(proc.stdout[:-1], encoding='UTF-8')

def metricToNumber(request):
    return int(request[12:-14])

def temperatureConversion(temp):
    return float(temp[:-1]) / 1000


startTime = time.monotonic()
prevMetrics = dict()
while (time.monotonic() - startTime) < EXPERIMENT_TIME:
    startSample = time.monotonic()
    proc = subprocess.run(['kubectl', 'get', 'pods'], capture_output=True)
    pods = proc.stdout.split(b'\n')

    arrayCalculatorMetrics = list()
    sqrtLooperMetrics = list()
    for pod in pods[1:-1]:
        podName = pod[:pod.find(b' ')]
        if podName.find(b'prometheus-adapter') >= 0:
            continue
        elif podName.find(b'array-calculator') >= 0:
            arrayCalculatorPod = True
        else:
            arrayCalculatorPod = False
        ipAddress = getIP(podName)
        curlCommand = '{ipAddress}:{port}/metric'
        if arrayCalculatorPod:
            portNum = str(8888)
        else:
            portNum = str(9999)
        curlCommand = curlCommand.format(ipAddress=ipAddress, port=portNum)
        proc = subprocess.run(['kubectl', 'exec', podName, '--', 'curl', curlCommand], capture_output=True)
        metric = metricToNumber(proc.stdout)

        rate = 0
        try:
            prevMetric, timeIndex = prevMetrics[podName]
            change = metric - prevMetric
            if change < 0:
                change *= -1
            rate = change / (time.monotonic() - timeIndex)
        except KeyError:
            pass
        prevMetrics[podName] = (metric, time.monotonic())

        if arrayCalculatorPod:
            arrayCalculatorMetrics.append(rate)
        else:
            sqrtLooperMetrics.append(rate)

        if random.random() < RESTART_RATIO:
            subprocess.run(['kubectl', 'delete', 'pod', podName, '&'], shell=True, capture_output=True)
    
    for i in range(1,5):
        proc = subprocess.run(['kubectl', 'get', '--raw', '/apis/custom.metrics.k8s.io/v1beta1/nodes/node{}-pentapod/node_thermal_zone_temp'.format(i)], capture_output=True)
        nodeInfo = json.loads(str(proc.stdout, encoding='UTF-8'))
        temp = temperatureConversion(nodeInfo['items'][0]['value'])
        with open('node{}-temperature.csv'.format(i), 'a') as f:
            f.write(str(time.monotonic()-startTime) + ',' + str(temp) + '\n')


    with open('cool-throughput.csv', 'a') as f:
        f.write(str(time.monotonic()-startTime) + ',' + str(statistics.mean(arrayCalculatorMetrics)) + '\n')
    with open('hot-throughput.csv', 'a') as f:
        f.write(str(time.monotonic()-startTime) + ',' + str(statistics.mean(sqrtLooperMetrics)) + '\n')

    sampleDuration = time.monotonic() - startSample
    if sampleDuration <= SAMPLE_TIME:
        time.sleep(SAMPLE_TIME - sampleDuration)

