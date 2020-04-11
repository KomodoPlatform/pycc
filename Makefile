
build:
	cargo +nightly build --release

cargo-watch-test:
	cargo +nightly watch -x "test --no-default-features"
