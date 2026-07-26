JAR = build/diffrun.jar
MANIFEST = build/MANIFEST.MF
CLASSES = build/classes

SRC = \
	runner/Main.java \
	runner/Types.java \
	runner/Checks.java \
	k7m/PhaseFold.java \
	k7m/ShadowClip.java \
	n3p/MuxQ3.java \
	n3p/SideAux.java \
	q2s/PhaseQ2.java \
	q2s/FrameQ7.java \
	readers/SliceQ7.java \
	readers/TableQ5.java

.PHONY: all clean

all: $(JAR)

$(CLASSES):
	mkdir -p $(CLASSES)

$(MANIFEST): | $(CLASSES)
	printf 'Manifest-Version: 1.0\nMain-Class: runner.Main\n' > $(MANIFEST)

$(JAR): $(SRC) $(MANIFEST) | $(CLASSES)
	javac -d $(CLASSES) $(SRC)
	jar cfm $(JAR) $(MANIFEST) -C $(CLASSES) .

clean:
	rm -rf build
