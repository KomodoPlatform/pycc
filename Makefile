
pycctx:
	cargo +nightly build --release

cargo-watch-test:
	cargo +nightly watch -x "test --no-default-features"

cargo-watch-build:
	cargo +nightly watch -w src -x "build"
