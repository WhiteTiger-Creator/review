package com.marlin.app;

public final class SlotCtx {
    private int chronoMark;
    private int boundFlag;
    private int staleFlag;
    private int freshness;
    private int boundLead;
    private int winLo;
    private int winHi;
    private String pairId = "";
    private String side = "";
    private String wave = "";
    private String pack = "";
    private byte[] boundBytes;

    public SlotCtx copy() {
        SlotCtx c = new SlotCtx();
        c.chronoMark = chronoMark;
        c.boundFlag = boundFlag;
        c.staleFlag = staleFlag;
        c.freshness = freshness;
        c.boundLead = boundLead;
        c.winLo = winLo;
        c.winHi = winHi;
        c.pairId = pairId;
        c.side = side;
        c.wave = wave;
        c.pack = pack;
        if (boundBytes != null) {
            c.boundBytes = boundBytes.clone();
        }
        return c;
    }

    public int chronoMark() { return chronoMark; }
    public void setChronoMark(int v) { chronoMark = v; }
    public int boundFlag() { return boundFlag; }
    public void setBoundFlag(int v) { boundFlag = v; }
    public int staleFlag() { return staleFlag; }
    public void setStaleFlag(int v) { staleFlag = v; }
    public int freshness() { return freshness; }
    public void setFreshness(int v) { freshness = v; }
    public int boundLead() { return boundLead; }
    public void setBoundLead(int v) { boundLead = v; }
    public int winLo() { return winLo; }
    public void setWinLo(int v) { winLo = v; }
    public int winHi() { return winHi; }
    public void setWinHi(int v) { winHi = v; }
    public String pairId() { return pairId; }
    public void setPairId(String v) { pairId = v; }
    public String side() { return side; }
    public void setSide(String v) { side = v; }
    public String wave() { return wave; }
    public void setWave(String v) { wave = v; }
    public String pack() { return pack; }
    public void setPack(String v) { pack = v; }
    public byte[] boundBytes() { return boundBytes; }
    public void setBoundBytes(byte[] v) { boundBytes = v; }
}
