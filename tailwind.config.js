import defaultTheme from 'tailwindcss/defaultTheme';
import forms from '@tailwindcss/forms';

/** @type {import('tailwindcss').Config} */
export default {
    content: [
        './vendor/laravel/framework/src/Illuminate/Pagination/resources/views/*.blade.php',
        './storage/framework/views/*.php',
        './resources/views/**/*.blade.php',
    ],

    theme: {
        extend: {
            fontFamily: {
                sans: ['Plus Jakarta Sans', ...defaultTheme.fontFamily.sans],
            },
            colors: {
                edic: {
                    accent:       '#0d9488',
                    'accent-bright': '#00d4aa',
                    'accent-dark':   '#0f766e',
                    'accent-light':  '#e6faf6',
                    sidebar:      '#1a1e2e',
                    bg:           '#f4f7f9',
                },
            },
        },
    },

    plugins: [forms],
};
