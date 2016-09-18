Idle at start: 220uA
Read: 700uA


Read every 2s:
    $ hcitool lecup  --handle=<HANDLE> --min 6 --max 50 --timeout 1000 --latency 0
    idle: 85uA
    read time: 0.7s

    $ hcitool lecup  --handle=<HANDLE> --min 6 --max 100 --timeout 1000 --latency 0
    idle: 55uA
    read time: 1.4s

    $ hcitool lecup  --handle=<HANDLE> --min 6 --max 150 --timeout 1000 --latency 0
    idle: 35uA
    read time: 2s

