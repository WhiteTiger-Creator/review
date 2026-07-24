package com.culvert.io;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

public final class Loader {
    private static final Gson GSON = new Gson();

    public record Node(String id, double[] features) {}

    public record Case(String name, Node[] nodes, List<String> marks) {}

    public static Case load(Path path) throws IOException {
        String text = Files.readString(path);
        JsonObject root = GSON.fromJson(text, JsonObject.class);
        String name = root.get("name").getAsString();
        JsonArray arr = root.getAsJsonArray("nodes");
        List<Node> nodes = new ArrayList<>();
        for (JsonElement el : arr) {
            JsonObject obj = el.getAsJsonObject();
            String id = obj.get("id").getAsString();
            JsonArray feat = obj.getAsJsonArray("features");
            double[] vec = new double[feat.size()];
            for (int i = 0; i < feat.size(); i++) {
                vec[i] = feat.get(i).getAsDouble();
            }
            nodes.add(new Node(id, vec));
        }
        List<String> marks = new ArrayList<>();
        if (root.has("marks")) {
            for (JsonElement el : root.getAsJsonArray("marks")) {
                marks.add(el.getAsString());
            }
        }
        return new Case(name, nodes.toArray(new Node[0]), marks);
    }
}
