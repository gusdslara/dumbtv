package tv.dumbtv.home;

import android.animation.Animator;
import android.animation.AnimatorSet;
import android.animation.ObjectAnimator;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Handler;
import android.os.Looper;
import android.service.dreams.DreamService;
import android.util.DisplayMetrics;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.animation.DecelerateInterpolator;
import android.view.animation.LinearInterpolator;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextClock;
import android.widget.TextView;

import java.io.File;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.Random;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * The screensaver (a DreamService, picked with settings secure screensaver_components): local
 * images cross-fade with a slow zoom, under a caption and a clock. scripts/screensaver.sh pushes
 * the images into the app's media folder, the one adb can write on every Fire OS, so the app
 * still needs no internet and no permission. A file named "Category - Title - 1.jpg" is shown
 * as category above title.
 */
public final class Screensaver extends DreamService {
    /** Next to home.conf and the wallpapers: /sdcard/Android/media/tv.dumbtv.home/screensaver. */
    static final String FOLDER = "screensaver";
    private static final long SHOW_MS = 12_000;
    private static final long FADE_MS = 1_600;
    private static final long CAPTION_MS = 450;

    private final Handler ui = new Handler(Looper.getMainLooper());
    private final ExecutorService loader = Executors.newSingleThreadExecutor();
    private final Random random = new Random();
    private final ImageView[] screens = new ImageView[2];
    private final Bitmap[] bitmaps = new Bitmap[2];
    private final AnimatorSet[] animations = new AnimatorSet[2];
    private final List<File> queue = new ArrayList<>();

    private TextView category;
    private TextView title;
    private LinearLayout caption;
    private int current = 0;
    private int next = 0;
    private int failures = 0;
    private int width = 1920;
    private int height = 1080;
    private volatile boolean running;

    @Override
    public void onAttachedToWindow() {
        super.onAttachedToWindow();
        setInteractive(false);
        setFullscreen(true);
        setScreenBright(true);

        DisplayMetrics dm = getResources().getDisplayMetrics();
        width = Math.max(dm.widthPixels, 1280);
        height = Math.max(dm.heightPixels, 720);

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.BLACK);

        for (int i = 0; i < 2; i++) {
            ImageView v = new ImageView(this);
            v.setScaleType(ImageView.ScaleType.CENTER_CROP);
            v.setAlpha(0f);
            root.addView(v, full());
            screens[i] = v;
        }

        // Shade at the bottom (caption) and the top (clock) so white text stays readable.
        View bottomShade = new View(this);
        bottomShade.setBackground(new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
                new int[] {0x00000000, 0x00000000, 0x33000000, 0xD9000000}));
        root.addView(bottomShade, full());
        View topShade = new View(this);
        topShade.setBackground(new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
                new int[] {0x99000000, 0x00000000}));
        root.addView(topShade, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, dp(200), Gravity.TOP));

        TextClock clock = new TextClock(this);
        clock.setFormat24Hour("HH:mm");
        clock.setFormat12Hour("h:mm");
        style(clock, 44, "sans-serif-light", 1f);
        FrameLayout.LayoutParams clockLp = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.WRAP_CONTENT,
                Gravity.TOP | Gravity.END);
        clockLp.setMargins(0, dp(40), dp(64), 0);
        root.addView(clock, clockLp);

        caption = new LinearLayout(this);
        caption.setOrientation(LinearLayout.VERTICAL);
        category = new TextView(this);
        style(category, 16, "sans-serif-medium", 0.85f);
        category.setLetterSpacing(0.25f);
        title = new TextView(this);
        style(title, 40, "sans-serif-medium", 1f);
        title.setMaxWidth((int) (width * 0.7f));
        caption.addView(category);
        caption.addView(title);
        FrameLayout.LayoutParams captionLp = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.WRAP_CONTENT,
                Gravity.BOTTOM | Gravity.START);
        captionLp.setMargins(dp(72), 0, 0, dp(56));
        root.addView(caption, captionLp);

        setContentView(root);

        File folder = folder();
        load(folder);
        if (queue.isEmpty()) {
            category.setText("");
            title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 22);
            title.setText(getString(R.string.screensaver_empty, folder.getAbsolutePath()));
            return;
        }
        running = true;
        showNext();
    }

    @Override
    public void onDetachedFromWindow() {
        running = false;
        ui.removeCallbacksAndMessages(null);
        loader.shutdownNow();
        for (int i = 0; i < 2; i++) {
            if (animations[i] != null) animations[i].cancel();
            if (screens[i] != null) screens[i].setImageDrawable(null);
            if (bitmaps[i] != null) {
                bitmaps[i].recycle();
                bitmaps[i] = null;
            }
        }
        super.onDetachedFromWindow();
    }

    /** The media folder when there is one (adb writes there on Fire OS 8 too), else files/. */
    private File folder() {
        File[] media = getExternalMediaDirs();
        File base = (media != null && media.length > 0 && media[0] != null) ? media[0] : null;
        if (base == null) base = getExternalFilesDir(null);
        if (base == null) base = getFilesDir();
        return new File(base, FOLDER);
    }

    private void load(File folder) {
        queue.clear();
        File[] files = folder.listFiles();
        if (files == null) return;
        for (File f : files) {
            String n = f.getName().toLowerCase(Locale.ROOT);
            if (n.endsWith(".jpg") || n.endsWith(".jpeg") || n.endsWith(".png") || n.endsWith(".webp")) {
                queue.add(f);
            }
        }
        Collections.shuffle(queue, random);
        next = 0;
    }

    private void showNext() {
        if (!running || queue.isEmpty()) return;
        if (next >= queue.size()) {
            Collections.shuffle(queue, random);
            next = 0;
        }
        final File f = queue.get(next++);
        try {
            loader.execute(() -> {
                final Bitmap b = decode(f);
                ui.post(() -> show(b, f));
            });
        } catch (RuntimeException e) {
            // The executor is shut down: the screensaver is closing.
        }
    }

    /** Decodes the image already scaled down to the screen: a 1 GB stick has little to spare. */
    private Bitmap decode(File f) {
        try {
            BitmapFactory.Options o = new BitmapFactory.Options();
            o.inJustDecodeBounds = true;
            BitmapFactory.decodeFile(f.getAbsolutePath(), o);
            if (o.outWidth <= 0 || o.outHeight <= 0) return null;
            int sample = 1;
            while (o.outWidth / (sample * 2) >= width && o.outHeight / (sample * 2) >= height) sample *= 2;
            o = new BitmapFactory.Options();
            o.inSampleSize = sample;
            o.inPreferredConfig = Bitmap.Config.RGB_565;
            return BitmapFactory.decodeFile(f.getAbsolutePath(), o);
        } catch (Throwable t) {
            return null;
        }
    }

    private void show(Bitmap b, File f) {
        if (!running) {
            if (b != null) b.recycle();
            return;
        }
        if (b == null) {
            // A broken file is skipped, but a folder of broken files does not spin forever.
            if (++failures < queue.size()) ui.postDelayed(this::showNext, 300);
            return;
        }
        failures = 0;

        final int incoming = 1 - current;
        final ImageView in = screens[incoming];
        final ImageView out = screens[current];

        if (animations[incoming] != null) animations[incoming].cancel();
        Bitmap old = bitmaps[incoming];
        in.setImageBitmap(b);
        bitmaps[incoming] = b;
        if (old != null && old != b) old.recycle();

        // Slow zoom and drift (Ken Burns), in a random direction for each image.
        boolean zoomIn = random.nextBoolean();
        float zFrom = zoomIn ? 1.0f : 1.12f;
        float zTo = zoomIn ? 1.12f : 1.0f;
        float dx = (random.nextFloat() - 0.5f) * width * 0.05f;
        float dy = (random.nextFloat() - 0.5f) * height * 0.04f;
        in.setAlpha(0f);
        in.setScaleX(zFrom);
        in.setScaleY(zFrom);
        in.setTranslationX(-dx);
        in.setTranslationY(-dy);

        ObjectAnimator fadeIn = ObjectAnimator.ofFloat(in, View.ALPHA, 0f, 1f).setDuration(FADE_MS);
        fadeIn.setInterpolator(new DecelerateInterpolator());
        AnimatorSet drift = new AnimatorSet();
        drift.playTogether(
                ObjectAnimator.ofFloat(in, View.SCALE_X, zFrom, zTo),
                ObjectAnimator.ofFloat(in, View.SCALE_Y, zFrom, zTo),
                ObjectAnimator.ofFloat(in, View.TRANSLATION_X, -dx, dx),
                ObjectAnimator.ofFloat(in, View.TRANSLATION_Y, -dy, dy));
        drift.setDuration(SHOW_MS + FADE_MS * 2);
        drift.setInterpolator(new LinearInterpolator());
        AnimatorSet all = new AnimatorSet();
        all.playTogether(fadeIn, drift);
        animations[incoming] = all;
        in.setLayerType(View.LAYER_TYPE_HARDWARE, null);
        all.addListener(new LayerOff(in));
        all.start();

        ObjectAnimator.ofFloat(out, View.ALPHA, out.getAlpha(), 0f).setDuration(FADE_MS).start();

        setCaption(f);
        current = incoming;
        ui.postDelayed(this::showNext, SHOW_MS);
    }

    private void setCaption(File f) {
        final String[] parts = Caption.of(f.getName());
        caption.animate().cancel();
        caption.animate().alpha(0f).setDuration(CAPTION_MS).withEndAction(() -> {
            category.setText(parts[0].toUpperCase(Locale.getDefault()));
            category.setVisibility(parts[0].isEmpty() ? View.GONE : View.VISIBLE);
            title.setText(parts[1]);
            caption.animate().alpha(1f).setDuration(CAPTION_MS).start();
        }).start();
    }

    private void style(TextView v, int sp, String family, float alpha) {
        v.setTextColor(Color.WHITE);
        v.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        v.setTypeface(Typeface.create(family, Typeface.NORMAL));
        v.setShadowLayer(dp(6), 0, dp(1), 0xB3000000);
        v.setAlpha(alpha);
    }

    private static FrameLayout.LayoutParams full() {
        return new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT);
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    /** The hardware layer only helps while the alpha animates: drop it when the fade ends. */
    private static final class LayerOff implements Animator.AnimatorListener {
        private final View v;

        LayerOff(View v) {
            this.v = v;
        }

        @Override public void onAnimationEnd(Animator a) { v.setLayerType(View.LAYER_TYPE_NONE, null); }
        @Override public void onAnimationCancel(Animator a) { v.setLayerType(View.LAYER_TYPE_NONE, null); }
        @Override public void onAnimationStart(Animator a) { }
        @Override public void onAnimationRepeat(Animator a) { }
    }
}
