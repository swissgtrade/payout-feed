<?php
/**
 * Plugin Name: FirmUp Payout Carousel
 * Description: Carrousel de certificats payout pour swissfirmup.com (Elementor). Version tout-en-un.
 * Version: 1.0.2
 * Author: FirmUp
 */

if (!defined('ABSPATH')) {
    exit;
}

define('FIRMUP_PAYOUTS_VERSION', '1.0.2');
define('FIRMUP_PAYOUTS_POST_TYPE', 'firmup_payout');
define('FIRMUP_PAYOUTS_META_ID', 'firmup_payout_id');

add_action('init', 'firmup_payouts_register_post_type');
add_action('init', 'firmup_payouts_register_meta');
add_shortcode('firmup_payout_carousel', 'firmup_payouts_render_carousel');

function firmup_payouts_register_post_type(): void
{
    register_post_type(FIRMUP_PAYOUTS_POST_TYPE, [
        'labels' => [
            'name' => 'Payouts',
            'singular_name' => 'Payout',
            'add_new_item' => 'Ajouter un payout',
            'edit_item' => 'Modifier le payout',
            'all_items' => 'Tous les payouts',
        ],
        'public' => true,
        'publicly_queryable' => false,
        'show_ui' => true,
        'show_in_menu' => true,
        'show_in_rest' => true,
        'has_archive' => false,
        'menu_icon' => 'dashicons-awards',
        'supports' => ['title', 'thumbnail'],
        'rewrite' => false,
    ]);
}

function firmup_payouts_register_meta(): void
{
    register_post_meta(FIRMUP_PAYOUTS_POST_TYPE, FIRMUP_PAYOUTS_META_ID, [
        'type' => 'string',
        'single' => true,
        'show_in_rest' => true,
        'auth_callback' => static function (): bool {
            return current_user_can('edit_posts');
        },
    ]);
}

function firmup_payouts_inline_css(): string
{
    $path = plugin_dir_path(__FILE__) . 'assets/payout-carousel.css';
    if (is_readable($path)) {
        return (string) file_get_contents($path);
    }

    return '';
}

function firmup_payouts_inline_js(): string
{
    $path = plugin_dir_path(__FILE__) . 'assets/payout-carousel.js';
    if (is_readable($path)) {
        return (string) file_get_contents($path);
    }

    return '';
}

function firmup_payouts_enqueue_assets(): void
{
    wp_enqueue_style(
        'swiper',
        'https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.css',
        [],
        '11.2.10'
    );

    wp_register_style('firmup-payout-carousel', false, ['swiper'], FIRMUP_PAYOUTS_VERSION);
    wp_enqueue_style('firmup-payout-carousel');
    wp_add_inline_style('firmup-payout-carousel', firmup_payouts_inline_css());

    wp_enqueue_script(
        'swiper',
        'https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.js',
        [],
        '11.2.10',
        true
    );

    wp_register_script('firmup-payout-carousel', false, ['swiper'], FIRMUP_PAYOUTS_VERSION, true);
    wp_enqueue_script('firmup-payout-carousel');
    wp_add_inline_script('firmup-payout-carousel', firmup_payouts_inline_js());
}

/**
 * Shortcode: [firmup_payout_carousel slides="3" autoplay="5"]
 */
function firmup_payouts_render_carousel(array $atts = []): string
{
    $atts = shortcode_atts([
        'slides' => '3',
        'autoplay' => '5',
        'limit' => '50',
    ], $atts, 'firmup_payout_carousel');

    $posts = get_posts([
        'post_type' => FIRMUP_PAYOUTS_POST_TYPE,
        'post_status' => 'publish',
        'posts_per_page' => max(1, (int) $atts['limit']),
        'orderby' => 'date',
        'order' => 'DESC',
    ]);

    if (!$posts) {
        return '<div class="firmup-payout-carousel firmup-payout-carousel--empty">Aucun payout publié pour le moment.</div>';
    }

    firmup_payouts_enqueue_assets();

    $carousel_id = 'firmup-payout-carousel-' . wp_generate_uuid4();
    $slides_per_view = max(1, (int) $atts['slides']);
    $autoplay_delay = max(0, (int) $atts['autoplay']) * 1000;

    ob_start();
    ?>
    <div
        class="firmup-payout-carousel"
        id="<?php echo esc_attr($carousel_id); ?>"
        data-slides="<?php echo esc_attr((string) $slides_per_view); ?>"
        data-autoplay="<?php echo esc_attr((string) $autoplay_delay); ?>"
    >
        <div class="swiper firmup-payout-carousel__swiper">
            <div class="swiper-wrapper">
                <?php foreach ($posts as $post) : ?>
                    <?php
                    $image = get_the_post_thumbnail_url($post->ID, 'large');
                    if (!$image) {
                        continue;
                    }
                    ?>
                    <div class="swiper-slide firmup-payout-carousel__slide">
                        <div class="firmup-payout-carousel__card">
                            <img
                                class="firmup-payout-carousel__image"
                                src="<?php echo esc_url($image); ?>"
                                alt="<?php echo esc_attr(get_the_title($post)); ?>"
                                loading="lazy"
                                decoding="async"
                            />
                        </div>
                    </div>
                <?php endforeach; ?>
            </div>
            <div class="swiper-pagination firmup-payout-carousel__pagination"></div>
        </div>
    </div>
    <?php
    return (string) ob_get_clean();
}
