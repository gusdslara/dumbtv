package tv.dumbtv.home;

import java.util.Arrays;

/** Screensaver captions from file names: no Android runtime or device. */
public final class CaptionTest {
    private static void check(String name, String category, String title) {
        String[] got = Caption.of(name);
        if (!Arrays.equals(got, new String[] {category, title})) {
            throw new AssertionError(name + " -> " + Arrays.toString(got));
        }
    }

    public static void main(String[] args) {
        check("Marvel - Loki - 2.jpg", "Marvel", "Loki");
        check("Anime - Frieren Beyond Journey's End - 1.jpg", "Anime", "Frieren Beyond Journey's End");
        check("DC - Batman - The Animated Series - 1.png", "DC", "Batman - The Animated Series");
        check("Filme - 1917 - 1.jpg", "Filme", "1917");
        check("Beach.jpg", "", "Beach");
        check("sunset - 3.webp", "", "sunset");
        check("no-extension", "", "no-extension");
        check(".jpg", "", ".jpg");
        System.out.println("CaptionTest: ok");
    }
}
