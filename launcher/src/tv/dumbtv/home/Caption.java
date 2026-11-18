package tv.dumbtv.home;

import java.util.ArrayList;
import java.util.List;

/** The screensaver's caption from an image's file name. No Android: tested on the host. */
final class Caption {
    private Caption() {}

    /** "Marvel - Loki - 2.jpg" -> {"Marvel", "Loki"}; "Beach.jpg" -> {"", "Beach"}. */
    static String[] of(String name) {
        int dot = name.lastIndexOf('.');
        String base = dot > 0 ? name.substring(0, dot) : name;
        List<String> p = new ArrayList<>();
        for (String s : base.split(" - ")) if (!s.trim().isEmpty()) p.add(s.trim());
        // A trailing number only tells two images of one title apart.
        if (p.size() > 1 && p.get(p.size() - 1).matches("\\d+")) p.remove(p.size() - 1);
        if (p.size() >= 2) {
            StringBuilder t = new StringBuilder();
            for (int i = 1; i < p.size(); i++) {
                if (i > 1) t.append(" - ");
                t.append(p.get(i));
            }
            return new String[] {p.get(0), t.toString()};
        }
        return new String[] {"", p.isEmpty() ? base : p.get(0)};
    }
}
