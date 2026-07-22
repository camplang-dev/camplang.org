+++
title = "Features"
description = "A short overview of the language ideas that shape Camp."
weight = 20
+++

# Features

Camp is designed for native libraries, runtimes, bindings, embedded targets,
classic platforms, and other work where ABI boundaries matter.

## Native contracts in source

Allocation context, lifetimes, thrown values, callback ownership, and exported
ABI shape are part of Camp's source model instead of hidden conventions.

## Modern API surfaces

Camp has classes, structs, interfaces, generics, properties, iterators,
lambdas, async calls, overload selectors, named arguments, and documentation
comments. These features are selected to stay useful across native boundaries.

## C toolchain compatibility

Camp lowers through C and native toolchains. The generated C is an artifact, not
the language, but it keeps Camp practical on established platforms.

## Explicit interop

`export`, `extern`, `@symbol`, API metadata, package references, and target
definitions give Camp code a clear relationship with the systems around it.

