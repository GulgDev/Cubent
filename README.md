# Cubent

![Cubent](/cubent.png?raw=true)

Cubent is programming language for creating minecraft datapacks.

## File structure

Cubent file starts with imports and contains namespaces, load & tick blocks:
```cubent
import foo.bar as far;
import foo.baz;

namespace boo {
    // Functions
}

load {
    // Load datapack
}

tick {
    // Run every tick
}
```
Inside the namespace block you can define functions:
```cubent
namespace boo {
    function faz(arg: String): Void {
        // Code here
    }
}
```

## Compiling
Download the compiler and use `cubent -h` to get started.