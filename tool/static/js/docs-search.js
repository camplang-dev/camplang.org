(() => {
	let searchReady = false;
	let searchElement = null;

	function restoreSidebarScroll() {
		const docsNav = document.querySelector(".docs-nav--desktop");
		if (!docsNav || docsNav.dataset.scrollBound === "true") {
			return;
		}

		const key = "camp.docsNav.scrollTop";
		const scrollTop = Number.parseInt(sessionStorage.getItem(key) ?? "0", 10);
		if (Number.isFinite(scrollTop)) {
			docsNav.scrollTop = scrollTop;
		}

		docsNav.addEventListener("scroll", () => {
			sessionStorage.setItem(key, String(docsNav.scrollTop));
		}, { passive: true });
		docsNav.dataset.scrollBound = "true";
	}

	function initializeSearch() {
		const element = document.querySelector("#docs-search-ui");
		if (searchReady && searchElement === element) {
			return;
		}

		if (!window.PagefindUI) {
			console.error("Pagefind UI failed to load.");
			return;
		}

		new window.PagefindUI({
			element: "#docs-search-ui",
			showSubResults: true,
			showImages: false,
		});
		searchReady = true;
		searchElement = element;
	}

	function bindSearchButtons() {
		for (const button of document.querySelectorAll("[data-docs-search-open]")) {
			if (button.dataset.searchBound === "true") {
				continue;
			}

			button.addEventListener("click", () => {
				const dialog = document.querySelector("[data-docs-search-dialog]");
				if (!dialog) {
					return;
				}

				initializeSearch();
				dialog.showModal();
				window.setTimeout(() => {
					dialog.querySelector("input")?.focus();
				}, 0);
			});
			button.dataset.searchBound = "true";
		}

		for (const button of document.querySelectorAll("[data-docs-search-close]")) {
			if (button.dataset.searchBound === "true") {
				continue;
			}

			button.addEventListener("click", () => {
				button.closest("dialog")?.close();
			});
			button.dataset.searchBound = "true";
		}
	}

	function initDocsUi() {
		restoreSidebarScroll();
		bindSearchButtons();
	}

	window.CampDocs = window.CampDocs || {};
	window.CampDocs.init = initDocsUi;
	initDocsUi();
})();
