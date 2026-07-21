.PHONY: build run clean

build:
	CGO_ENABLED=1 go build -o jobqueue .

run: build
	DB_PATH=/opt/jobqueue/jobs.db PORT=8080 ./jobqueue

clean:
	rm -f jobqueue
