(() => {
	if (!window.Swup || !document.querySelector("#docs-swup")) {
		return;
	}

	const swup = new window.Swup({
		animationSelector: false,
		containers: ["#docs-swup"],
		linkSelector: "a[href^='/docs/']:not([target]):not([download])",
	});

	swup.hooks.on("visit:start", () => {
		const docsNav = document.querySelector(".docs-nav--desktop");
		if (docsNav) {
			sessionStorage.setItem("camp.docsNav.scrollTop", String(docsNav.scrollTop));
		}
	});

	swup.hooks.on("page:view", () => {
		window.CampDocs?.init?.();
	});
})();
