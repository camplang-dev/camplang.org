#!/usr/bin/env node
"use strict";

const fs = require("fs");
const http = require("http");
const https = require("https");
const path = require("path");

const root = path.resolve(__dirname, "..");
const certDir = path.join(root, ".local", "https");
const listenPort = Number(process.env.CAMP_HTTPS_PORT || "8443");
const targetHost = process.env.CAMP_HTTP_HOST || "127.0.0.1";
const targetPort = Number(process.env.CAMP_HTTP_PORT || "1111");

const options = {
	key: fs.readFileSync(path.join(certDir, "server.key.pem")),
	cert: fs.readFileSync(path.join(certDir, "server.fullchain.pem")),
};

const server = https.createServer(options, (request, response) => {
	const proxyRequest = http.request(
		{
			host: targetHost,
			port: targetPort,
			method: request.method,
			path: request.url,
			headers: {
				...request.headers,
				host: `${targetHost}:${targetPort}`,
			},
		},
		(proxyResponse) => {
			response.writeHead(proxyResponse.statusCode || 502, proxyResponse.headers);
			proxyResponse.pipe(response);
		}
	);

	proxyRequest.on("error", (error) => {
		response.writeHead(502, { "content-type": "text/plain" });
		response.end(`Unable to reach local Zola server at http://${targetHost}:${targetPort}/\n${error.message}\n`);
	});

	request.pipe(proxyRequest);
});

server.listen(listenPort, "0.0.0.0", () => {
	console.log(`HTTPS proxy available at https://0.0.0.0:${listenPort}/`);
	console.log(`Proxying http://${targetHost}:${targetPort}/`);
});
