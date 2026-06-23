(function () {
  function initCarousel(root) {
    if (!root || root.dataset.initialized === "1") {
      return;
    }

    var swiperEl = root.querySelector(".firmup-payout-carousel__swiper");
    if (!swiperEl || typeof Swiper === "undefined") {
      return;
    }

    var slides = parseInt(root.dataset.slides || "3", 10);
    var autoplayDelay = parseInt(root.dataset.autoplay || "0", 10);

    var config = {
      slidesPerView: 1,
      spaceBetween: 20,
      centeredSlides: false,
      loop: false,
      grabCursor: true,
      pagination: {
        el: root.querySelector(".firmup-payout-carousel__pagination"),
        clickable: true,
      },
      breakpoints: {
        768: {
          slidesPerView: Math.min(2, slides),
        },
        1200: {
          slidesPerView: slides,
        },
      },
    };

    if (autoplayDelay > 0) {
      config.autoplay = {
        delay: autoplayDelay,
        disableOnInteraction: false,
        pauseOnMouseEnter: true,
      };
    }

    var swiper = new Swiper(swiperEl, config);

    root.addEventListener("mouseenter", function () {
      if (swiper.autoplay && swiper.autoplay.running) {
        swiper.autoplay.stop();
      }
    });

    root.addEventListener("mouseleave", function () {
      if (swiper.autoplay && autoplayDelay > 0) {
        swiper.autoplay.start();
      }
    });

    root.dataset.initialized = "1";
  }

  function initAll() {
    document.querySelectorAll(".firmup-payout-carousel").forEach(initCarousel);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAll);
  } else {
    initAll();
  }
})();
