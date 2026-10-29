package com.vifasttts.mobile;

import android.app.Activity;
import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.view.View;
import android.view.Window;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Palette/font dùng chung với desktop/iOS/web (design/tokens.json). */
final class VfTheme {
    static final int BG = Color.rgb(0xFB, 0xF6, 0xEE);
    static final int SURFACE = Color.WHITE;
    static final int INK = Color.rgb(0x1F, 0x24, 0x30);
    static final int MUTED = Color.rgb(0x6B, 0x72, 0x80);
    static final int ACCENT = Color.rgb(0xC6, 0x28, 0x1E);
    static final int ACCENT_DARK = Color.rgb(0x99, 0x1B, 0x1B);
    static final int BORDER = Color.rgb(0xE8, 0xDD, 0xD0);
    static final int SOFT = Color.rgb(0xFB, 0xF0, 0xEC);
    static final int SUCCESS = Color.rgb(0x15, 0x80, 0x3D);
    static final int WARNING = Color.rgb(0xB4, 0x53, 0x09);
    static final int ERROR = Color.rgb(0xB9, 0x1C, 0x1C);

    private VfTheme() {}

    static void applyWindow(Activity activity) {
        Window window = activity.getWindow();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            window.setDecorFitsSystemWindows(false);
        }
        window.setStatusBarColor(BG);
        window.setNavigationBarColor(BG);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            window.getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);
        }
    }

    static Typeface typeface(Context context) {
        try {
            return Typeface.createFromAsset(context.getAssets(), "BeVietnamPro-Regular.ttf");
        } catch (Throwable ignored) {
            return Typeface.DEFAULT;
        }
    }

    static void text(TextView view, Typeface base, float size, int color, boolean bold) {
        view.setTextSize(size);
        view.setTextColor(color);
        view.setTypeface(bold ? Typeface.create(base, Typeface.BOLD) : base);
    }

    static void primaryButton(Button button, Typeface base) {
        button.setAllCaps(false);
        text(button, base, 16, Color.WHITE, true);
        button.setBackground(rounded(button.getContext(), ACCENT, ACCENT, 12, 1));
        int pad = dp(button.getContext(), 16);
        button.setPadding(pad, dp(button.getContext(), 12), pad, dp(button.getContext(), 12));
        button.setMinHeight(dp(button.getContext(), 48));
    }

    static void secondaryButton(Button button, Typeface base) {
        button.setAllCaps(false);
        text(button, base, 14, ACCENT_DARK, false);
        button.setBackground(rounded(button.getContext(), SOFT, BORDER, 12, 1));
        int pad = dp(button.getContext(), 12);
        button.setPadding(pad, dp(button.getContext(), 10), pad, dp(button.getContext(), 10));
        button.setMinHeight(dp(button.getContext(), 44));
    }

    /** Nút chip nhỏ cho ví dụ nhanh. */
    static void chipButton(Button button, Typeface base) {
        button.setAllCaps(false);
        text(button, base, 12, INK, false);
        button.setBackground(rounded(button.getContext(), SURFACE, BORDER, 999, 1));
        int pad = dp(button.getContext(), 10);
        button.setPadding(pad, dp(button.getContext(), 5), pad, dp(button.getContext(), 5));
        button.setMinHeight(dp(button.getContext(), 32));
    }

    static GradientDrawable background(Context context) {
        GradientDrawable drawable = new GradientDrawable(
                GradientDrawable.Orientation.TOP_BOTTOM,
                new int[]{BG, Color.rgb(0xFF, 0xF8, 0xF0)});
        return drawable;
    }

    /** Nút segmented Local/Remote giống Picker iOS. */
    static void segmentButton(Button button, boolean selected, Typeface base) {
        button.setAllCaps(false);
        text(button, base, 14, selected ? Color.WHITE : INK, selected);
        button.setBackground(rounded(
                button.getContext(),
                selected ? ACCENT : Color.TRANSPARENT,
                selected ? ACCENT : BORDER,
                9,
                1));
        button.setMinHeight(dp(button.getContext(), 38));
        button.setPadding(dp(button.getContext(), 12), dp(button.getContext(), 7),
                dp(button.getContext(), 12), dp(button.getContext(), 7));
    }

    /** Card surface nhẹ, cùng radius với iOS/web. */
    static void card(LinearLayout view) {
        view.setBackground(rounded(view.getContext(), SURFACE, BORDER, 16, 1));
        int pad = dp(view.getContext(), 16);
        view.setPadding(pad, pad, pad, pad);
    }

    static GradientDrawable dot(Context context, int color) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setShape(GradientDrawable.OVAL);
        drawable.setColor(color);
        int size = dp(context, 8);
        drawable.setSize(size, size);
        return drawable;
    }

    static void input(EditText input, Typeface base) {
        text(input, base, 14, INK, false);
        input.setHintTextColor(MUTED);
        input.setBackground(rounded(input.getContext(), SURFACE, BORDER, 9, 1));
        int pad = dp(input.getContext(), 10);
        input.setPadding(pad, dp(input.getContext(), 8), pad, dp(input.getContext(), 8));
    }

    static GradientDrawable rounded(Context context, int fill, int stroke, int radiusDp, int strokeDp) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(fill);
        drawable.setCornerRadius(dp(context, radiusDp));
        drawable.setStroke(dp(context, strokeDp), stroke);
        return drawable;
    }

    static int dp(Context context, int value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }
}
